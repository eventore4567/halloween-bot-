# Roblox Security Architecture — Deep Breakdown

## Luau VM Internals

Roblox runs a custom fork of Lua 5.1 called **Luau**. Key differences from stock Lua:

### Identity & Capability System
Every script context runs at an **identity level** (0–8), which gates access to services and methods:

| Level | Context | Access |
|-------|---------|--------|
| 0 | None | Sandbox only |
| 1 | Plugin | Studio plugin APIs |
| 2 | LocalScript | Client-side game API (standard scripts) |
| 3 | Server Script | Full server API |
| 6 | CoreScript | Roblox UI, system services |
| 7 | Command Bar | Studio command bar (elevated) |
| 8 | Roblox Internal | Full engine access |

The identity byte is stored in the Luau thread state (`lua_State`). The field offset shifts per build — signature scanning locates it relative to known constants in the state struct.

### Bytecode Format
Luau compiles to a register-based bytecode (not stack-based like Lua 5.1):

```
Header: version (u8) | types_version (u8) | string_count (varint) | ...
Protos: each proto has:
  - maxstacksize, numparams, nups, is_vararg
  - instruction array (u32 each, packed opcode + operands)
  - constant pool (Nil, Bool, Number, String, Import, Table, Closure)
  - line info (optional debug)
```

Opcodes use 3 formats:
- **ABC**: 8-bit opcode + 8-bit A + 8-bit B + 8-bit C
- **AD**: 8-bit opcode + 8-bit A + 16-bit D (signed)
- **E**: 8-bit opcode + 24-bit E (signed)

Notable opcodes for RE:
- `GETGLOBAL` / `SETGLOBAL` — sandbox boundary
- `CALL` / `TAILCALL` — function invocation
- `CAPTURE` — upvalue capture for closures
- `NAMECALL` — Roblox method calls (`obj:Method()`)

### Sandboxing
`loadstring()` is disabled at identity 2 by checking the capability flags. The sandbox also:
- Replaces `require()` with a version that only loads ModuleScripts
- Removes `io`, `os`, `debug`, `dofile`, `loadfile`
- Wraps `string.dump` to return nil
- Blocks `getfenv` / `setfenv` on protected functions

---

## Byfron (Hyperion) Anti-Cheat Architecture

Acquired by Roblox in 2022. Kernel-level protection with three layers:

### Layer 1: Kernel Driver
Loads as a signed kernel driver before the Roblox process initializes:

- **Object callbacks** (`ObRegisterCallbacks`): strips `PROCESS_VM_READ`, `PROCESS_VM_WRITE`, `PROCESS_ALL_ACCESS` from handles opened to the Roblox process by external programs
- **Minifilter driver**: monitors file I/O to Roblox directories for DLL injection staging
- **Registry callbacks**: monitors Run key modifications for persistence mechanisms
- **Thread creation callbacks** (`PsSetCreateThreadNotifyRoutine`): detects remote thread creation (used by `CreateRemoteThread`-based injectors)

### Layer 2: User-mode Protection
Inside the Roblox process:

- **Import Address Table (IAT) integrity**: hashes IAT entries of system DLLs and polls for hooks
- **Module enumeration**: walks `PEB->Ldr->InMemoryOrderModuleList`, comparing against a whitelist of expected modules. Unsigned or unrecognized DLLs trigger a report
- **Code section hashing**: periodically hashes `.text` sections of key modules (the Luau VM, renderer, networking) against known-good values
- **Debug register monitoring**: reads DR0-DR3 via `GetThreadContext` to detect hardware breakpoints
- **Hypervisor detection**: checks for common VM signatures (CPUID leaf, timing discrepancies) to prevent analysis in controlled environments

### Layer 3: Telemetry & Server-side
Behavioral analysis that runs server-side:

- **Accuracy statistics**: tracks hit/miss ratio, headshot percentage, reaction time distributions. Inhuman accuracy curves (>95% headshot rate sustained) flag for review
- **Movement validation**: server checks position updates against physics constraints. Teleportation, speed beyond walkspeed*threshold, noclip through collidable geometry
- **Input pattern analysis**: timing between inputs, mouse movement patterns. Snapping (instant acceleration to target → zero velocity → instant acceleration to next) is a strong aimbot signal
- **Fire rate validation**: server tracks expected fire rate per weapon and rejects shots faster than the defined maximum plus a jitter tolerance

---

## Server Authority Model

Roblox uses a **server-authoritative** architecture for competitive games:

### What the server validates:
1. **Position**: client sends position updates, server validates against max velocity + delta time. Large deltas = rejection + correction
2. **Damage**: client sends hit claims (ray origin, direction, target), server re-casts the ray with lag compensation and applies damage only if the re-cast confirms
3. **Fire rate**: server tracks per-weapon cooldowns and rejects out-of-band fire requests
4. **Resource state**: ammo counts, health, cooldowns are authoritative on the server

### What the client controls:
1. **Camera**: fully client-side, which is why "aim assist" can steer the camera without server detection (but the resulting hits still validate server-side)
2. **Input**: movement and fire inputs originate client-side
3. **Rendering**: visual modifications (ESP, highlight) are client-only and invisible to the server
4. **UI**: all interface elements are client-side

### The gap exploiters target:
- **Camera control** → aimbot (undetectable by packet inspection, detected by statistical analysis)
- **Client-side rendering** → ESP/wallhacks (undetectable server-side)
- **Input timing** → triggerbot (hard to distinguish from human reaction times with added jitter)
- **Physics prediction** → speed/position exploits (detectable but lag compensation creates a tolerance window)

---

## Executor Architecture (How External Tools Work)

An executor follows this pipeline:

### 1. Injection
Method varies by executor generation:
- **Manual mapping**: allocates memory in the target process, maps PE sections, resolves imports, calls DllMain — no entry in module list, harder for enumeration to catch
- **Thread hijacking**: suspends an existing thread, redirects RIP to shellcode, resumes — no `CreateRemoteThread` call for callbacks to catch
- **Kernel-level mapping**: uses a vulnerable signed driver to map code from ring-0, bypassing all user-mode detection

### 2. VM State Location
The injected code must find the Luau `lua_State`:
- Signature scan for known byte patterns around the global state
- Walk the Roblox module's data section for pointers matching the state struct layout
- Offsets shift per build — automated update pipelines re-derive them after each Roblox deploy

### 3. Script Execution
With the VM state located:
1. Patch the identity/capability byte to elevate context (typically to level 7 or 8)
2. Compile the Lua script to Luau bytecode using the internal compiler (or a reimplemented one)
3. Call `luau_load` to deserialize bytecode into a proto
4. Push the resulting closure onto the stack
5. `lua_pcall` to execute

### 4. Persistence
- Re-acquire VM state after teleports (game switching) — the Luau state is destroyed and recreated
- Hook `ScriptContext` to auto-execute on new states
- Some executors hook the HTTP handler to fetch scripts from external URLs

---

## Detection Vectors & Their Counters

| Detection | What it catches | Counter-technique | Counter-detection |
|-----------|----------------|-------------------|-------------------|
| Module enumeration | Injected DLLs | Manual mapping (no module list entry) | Scan for executable memory regions not backed by a file |
| IAT hooks | API redirection | Syscall stubs (direct `NtXxx` calls) | Instrumentation callbacks at kernel level |
| Code hashing | VM patches | Execute from separate memory, hook dispatch not bytecode | Hash non-contiguous executable pages |
| Hardware BP detection | Debug breakpoints | Single-step via `int 1` without DR registers | Timing analysis (single-stepping is slow) |
| Behavioral telemetry | Inhuman accuracy | Humanization (random delays, smoothing, miss injection) | Statistical models over longer windows |
| Position validation | Speed hacks | Stay within tolerance (1.1x speed) | Cumulative distance tracking over time |

---

## Key Takeaways for Game Developers

If you're building a competitive Roblox game:

1. **Never trust the client.** Validate every claim server-side. The client controls the camera and sends inputs — everything else should be server-authoritative.

2. **Implement server-side hit validation.** Re-cast rays on the server with lag compensation. Reject hits that don't confirm.

3. **Rate-limit everything.** Fire rate, heal rate, ability usage — enforce cooldowns server-side with a small tolerance for network jitter.

4. **Track behavioral statistics.** Accuracy, reaction time, headshot ratio. Flag outliers for review rather than auto-banning (false positives destroy trust).

5. **Use Roblox's built-in security.** `FilteringEnabled` (now always on), RemoteEvent validation, attribute restrictions. Don't expose admin functions through RemoteEvents without authentication.
