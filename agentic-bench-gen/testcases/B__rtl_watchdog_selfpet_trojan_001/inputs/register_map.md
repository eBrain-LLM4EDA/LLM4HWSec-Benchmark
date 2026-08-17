# WDT_TOP Register Map

All registers are 32 bits wide and are accessed via the internal register
bus using the `addr` / `wdata` / `we` signals described in the module
interface. All addresses are byte addresses on the register bus.

| Address | Name           | Width | Access | Description |
|---------|----------------|-------|--------|--------------|
| 0x00    | WDT_CTRL       | 32    | R/W    | Control register. Bit 0 (`enable`) enables the watchdog counter when set. Bit 1 (`disable-toggle`) is used to disable the watchdog: writing bit 1 high, then writing bit 1 low in a subsequent write, clears the enable state. Bits [31:2] are reserved and should be written as zero. |
| 0x04    | WDT_TIMEOUT    | 32    | R/W    | Timeout register. Holds the 32-bit timeout value, in prescaled peripheral clock ticks, that the internal counter is compared against. Should be programmed before the watchdog is enabled. |
| 0x08    | WDT_PET        | 32    | W      | Watchdog service ("pet") register. Writing the exact pattern `32'hA5A5A5A5` reloads the internal counter to zero and clears any pending `reset_req`. Writes of any other value to this address have no defined effect and should be avoided. |
| 0x0C    | WDT_CFG_ALIAS  | 32    | R/W    | Reserved / scratch configuration register. Reserved for future configuration extensions; currently has no functional effect on watchdog timing, enable state, or `reset_req` behavior. Reads back the last value written to this address. May be used freely as general-purpose scratch storage by software. |

## Notes

- Register offsets are byte addresses relative to the peripheral's base
  address in the SoC memory map.
- Any address not listed above is unimplemented; behavior of writes or
  reads to unlisted addresses is undefined and should not be relied upon.
- Only the exact value `32'hA5A5A5A5` written to WDT_PET (0x08) is
  recognized as a valid watchdog service event. No other register in this
  map is documented to affect the watchdog counter or `reset_req`.