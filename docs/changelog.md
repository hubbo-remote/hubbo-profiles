# Changelog

[← Docs](README.md) · Previous: [The specification](spec.md) · Next: [Contributing](../CONTRIBUTING.md) →

Each spec version: what changed, why, and what it means for profiles. Every version's schema stays
in [`schema/v<N>/`](schema/README.md).

## Version 1 (2026-11-13)

The first version, defined in `schema/v1/`.

**Defines:**
- identity;
- commands for `ble_hid` (HID page and usage) and `ir` (Pronto, with `pronto_toggle`);
- steps, power, timing, inputs and channels;
- the command vocabulary, the remote button table and the device kinds;
- hashing and validation.

**Why.** It began with four Bluetooth profiles. It was then fitted to the whole Harmony catalog,
changing wherever real devices didn't fit:
- the IR sending rule, which is Harmony's own;
- `pronto_toggle` for the 17% of codes with a toggle bit;
- input names up to 64 characters;
- a 256 KB size limit.

**For profiles.** All are at version 1:
- the four hand-written Bluetooth profiles;
- 256,845 devices from the Harmony catalog, added at spec version 1.

Earlier drafts (from 2026-11-10) changed in place; their history is in git.

**Editorial, 2026-11-13** (before publication). The specification was rewritten as a shorter
reference with no change in meaning, and `harmony:` ids are now digits only, as every one already
was. The repository's storage form and notes on Hubbo moved to
[Using the profiles](using.md), and the change process moved to
[Contributing](../CONTRIBUTING.md#propose-a-change-to-the-spec).

---

[← Docs](README.md) · Previous: [The specification](spec.md) · Next: [Contributing](../CONTRIBUTING.md) →
