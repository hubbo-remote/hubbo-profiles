# Hubbo Device Profiles

These are the device profiles that power [Hubbo](https://github.com/maddox/hubbo), an open
replacement for the Harmony Hub.

## Why we keep them

Devices outlive the companies and servers that knew how to control them. The TV still works long
after its remote is lost and the service that knew its codes has shut down. These profiles keep
that knowledge open, free and kept for good, for anyone who owns the devices.

It's preservation, and it's a gift. Use them in Hubbo, in something of your own, or just to keep a
favorite old receiver running.

## What's here

- **An open spec** for describing how to control a device: its commands, how to turn it on and
  off, its timing, its inputs.
- **A library of profiles** written in it, covering decades of devices: about 257,000 of them,
  from 7,000 manufacturers.

## Read more

- [The specification](docs/spec.md)
- [Changelog](docs/changelog.md)
- [Contributing](CONTRIBUTING.md)

## Acknowledgements

The Harmony profiles are converted from the
[Logitech Harmony IR archive](https://github.com/pickysysadmin/logitech-harmony-ir-archive) by
pickysysadmin. Thank you for preserving it.

That archive was built with the help of these projects, and we're grateful to them too:

- Logitech, for compiling all of these codes
- [Flipper-IRDB](https://github.com/Lucaslhm/Flipper-IRDB)
- [IrScrutinizer](https://github.com/bengtmartensson/IrScrutinizer)
- [IrpTransmogrifier](https://github.com/bengtmartensson/IrpTransmogrifier)
- [MakeHex](https://github.com/probonopd/MakeHex)
- [irdb](https://github.com/probonopd/irdb)
- [Remote Central](https://www.remotecentral.com/cgi-bin/codes/)
- [harmony-hub-root](https://github.com/Ripthulhu/harmony-hub-root)

## License

Our contributions, meaning the specification, the schemas, the profile format and the conversion
and organization of the data, are released under [CC0 1.0 Universal](LICENSE).

The underlying IR codes originate with Logitech. We make no representation about their copyright
status, and we're not in a position to license them. CC0 waives our rights, not anyone else's. If
you're building something commercial on this, evaluate that yourself.
