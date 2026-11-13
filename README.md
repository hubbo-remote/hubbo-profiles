# Hubbo Profiles

**Open profiles for controlling the devices you own.** Free for everyone, kept for good.

Every TV, receiver, disc player, streamer and set-top box has its own way of being told what to
do: which codes it listens for, how to turn it on, how long it needs before it's ready, which
button picks HDMI 2. This is a library of that knowledge, written down in one open, documented
format, so anyone can use it.

There are about **257,000 devices from 7,000 manufacturers** here, each one a small JSON file
you can read, use and improve.

## Why it's open

Remote controls come and go, and the companies behind them stop running their servers. What a
device needs to be controlled shouldn't disappear with them. So every profile here is public, in a
format anyone can read, with a spec anyone can build on. See every profile, use it in anything you
make, download the whole library, and fix what's wrong.

It's used by [Hubbo](docs/README.md#what-uses-these-profiles), an open replacement for the
Harmony Hub, but it isn't only for Hubbo. Any program that sends infrared codes or Bluetooth keys
can use these profiles.

## Find a device

Each device is one file, named by its id:

- **Hand-written profiles** are in [`profiles/hubbo/`](profiles/hubbo/), such as
  [`apple-tv.json`](profiles/hubbo/apple-tv.json).
- **Devices from the Harmony catalog** are in `profiles/harmony/`: `harmony:498661` is
  [`profiles/harmony/498/498661.json`](profiles/harmony/498/498661.json). Their commands are
  kept once in [`codesets/`](codesets/) and shared by every device that uses them.

[Using the profiles](docs/using.md) explains how to read a file and find the device you want.

## Download everything

- **Clone it:** `git clone https://github.com/maddox/hubbo-profiles`
- **Or download a release:** each [release](https://github.com/maddox/hubbo-profiles/releases)
  has the whole library, with a search index, as one archive.

## Help improve it

Found a button that doesn't work, or a device that's missing? [Open an
issue](https://github.com/maddox/hubbo-profiles/issues/new/choose); no code needed. To fix a profile
or add a device yourself, the [contributing guide](CONTRIBUTING.md) walks you through it.

## The docs

- [Using the profiles](docs/using.md): find a device, read a profile, download them all
- [The specification](docs/spec.md): every field, the command names, the rules
- [Changelog](docs/changelog.md): each version of the spec, and what it meant for profiles
- [Contributing](CONTRIBUTING.md): fix a profile, add a device, propose a change

## License

Everything here (the profiles, the spec and the schemas) is dedicated to the public domain under
[CC0 1.0](LICENSE). Use it for anything, with no permission needed and no attribution required.
