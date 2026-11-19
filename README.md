# Shakra

A multifunctional Discord bot covering a wide range of features, tailored for the needs of the Hollow Knight Speedrun & Racing Community.

This rewrite moves most functionality (especially admin-only functionality) to the modern Discord Interaction model. Text command functionality is dropped, and if it comes back will be limited to a few public-facing commands.

## Features

- [x] Moderation features including ban reason DMs, message relay
    - [ ] (NEW) Ban appeal system, not requiring server membership to appeal
    - [ ] (NEW) Private ticketing system, a la modmail
        - Uses a forum for tickets & allows discussion without responding in the same thread.
- [x] Text tags accessible both by slash and text command
- [ ] Message logging to a channel, including edited & deleted messages
- [x] Race utilities, including countdown and react-to-ready
    - [x] Including text command fallbacks
- [x] Roles based off linked Speedrun.com profile
    - [ ] (NEW) Allow selecting a colour role based off existing roles (might be more generic)
- [x] Speedrun.com queue tracking system
    - [ ] (NEW) Maybe sync queue to SRC based on linked profile? 
- [ ] (NEW) Role selectors using modern Components v2 as an alternative to react roles.
- [ ] (NEW) Vote aid; only show link to members who press a button, checking they have correct role & recording they clicked.
- [ ] (NEW) Autoreact in forums
- [ ] (NEW) _maybe_ Roll-in Sheo/Quirrel functionality alongside HKC live check

### Deprecated Features

- React roles - might make sense to keep in? Or do we just accept id:customize?
- Tiered mutes - weren't seeing much usage and seem like more effort to set up per-guild than it's worth vs just manually assigning roles
    - These mutes were very often indefinite and so the main benefit got destroyed

## TODO

- [ ] Cooldowns
- [ ] Better per-server configurability on a cog registration level
    - [ ] Including better live reload to avoid needing admin maintenance on new guild joins.
- [ ] 

## Usage

- `uv run --frozen --env-file .env shakra`

Note that the lockfile includes more dependencies than may be necessary; you can use `--extra <name>` to select individual dependencies separate from the lockfile.

The following environment variables are required; the above assumes a `.env` file in the project root. This should contain:
- `TOKEN`: Discord API token
- `SRC_TOKEN`: Speedrun.com PHPSESSID cookie (for APIv2 integrations)
- `TWITCH_APPID`
- `TWITCH_SECRET`