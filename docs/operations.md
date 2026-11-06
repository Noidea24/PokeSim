# Operating PokeSim

These instructions cover the current Adventure Library. Older single-game instructions
are preserved in the [legacy operations archive](history/operations-legacy.md).
For installation, ports, permissions, and remote access, use [self-hosting](self-hosting.md).

## Start and stop

Desktop: run the launch command printed by the installer, or `pokesim-desktop` after
setting up PATH. Choose **Save and quit** to save all adventures and close the application.
Closing the browser tab leaves the application running.

Docker: run commands from the installation folder containing your Compose file:

```sh
docker compose up -d --wait
docker compose ps
docker compose logs --tail=100 pokesim
docker compose stop
```

Use the same Compose files and project name every time. One manager owns the complete
library and starts one child process for each running adventure. Never run two managers
against the same library or remove their lock files while they are running.

## Trainer and rival names

New adventures prefill trainer and rival names from the shared 30-name list.
Edit either field or use its **Randomize** button before creating the adventure.
Names accept 1 to 7 letters A to Z and are saved in uppercase. The simulation
enters the chosen names through the normal intro menus. The adventure’s library
label is separate. Existing adventures are not renamed, and older adventures
without these settings continue choosing intro names randomly.

## Custom nicknames

To turn nicknames off, open **Settings → Edit nickname pool**, check **Keep species names**
and save. Red, Blue and Yellow answer NO at the nickname prompt. Gold, Silver and Crystal
confirm a blank name, which the cartridge turns into the species name. League rewards and
Mew gifts also keep their species names. The word lists stay saved for when you turn it back
off. Like other nickname settings, it applies to future names in every adventure and never
renames existing Pokémon.

Open Library **Settings → Edit nickname pool**. Add prefixes, suffixes, or complete
names. Uncheck built-in entries you do not want, or paste exclusions under
**Excluded words and exact names**. Prefix and suffix exclusions affect generated
combinations. Full-name exclusions remove that exact name from every source,
including handwritten names and generated combinations.

Separate entries with commas or new lines. Prefix and suffix lists accept up to
100 entries of 1 to 7 letters each. Full-name lists accept up to 500 entries of
1 to 10 letters each. Entries use A to Z and are uppercased automatically.
Combinations longer than ten letters are skipped. The editor previews the number
of available names, and saving an empty pool is rejected.

The built-in vocabulary contains 100 prefixes, 70 suffixes and 100 handwritten
names, yielding 6,117 distinct valid nicknames. Every species draws from the same
pool, with no preference based on species, type, power or DVs. Written names have
the same selection weight as generated names.

Normal naming avoids names remembered by that adventure’s naming controller,
plus the current party, player and rival names, until its pool is exhausted.
League gifts use a separate deterministic draw without duplicate avoidance.
Different adventures and incoming trades can also introduce matching names.
The larger pool reduces collisions but does not guarantee library-wide uniqueness.

Saving applies to future names in running and stopped adventures. A name already
being entered finishes unchanged. League reward nicknames also use this pool.
Existing Pokémon, trainer names, and rival names are not renamed. **Reset editor to defaults** clears additions and exclusions in the editor.
Choose **Save nickname settings** to apply the reset. These settings are stored in the Library registry and
included in full Library backups. Reconnecting workers retry the saved settings.

## Extra store items

Gold, Silver and Crystal adventures have an **Extra store items** setting in the Library,
on by default for new adventures and changeable while the adventure is stopped. It lets the
Goldenrod Dept. Store sell evolution stones (2100 each) and the King’s Rock, Metal Coat, Dragon
Scale and Up-Grade, so a spent one-time item never blocks a Pokédex entry. Turn it off to keep
the store’s normal stock. After the Hall of Fame it also opens the TM shop (one-time TMs at
Goldenrod 5F) and the Champion shop (supplies at 4F); see
[Gen II exploration](gen2-exploration.md). `tools/play_gen2.py --extra-store-items` turns it on
for a scenario run.

## Fair wild DVs

Red, Blue and Yellow adventures have a **Fair wild DVs** setting in the Library, off by default
and changeable while the adventure is stopped. The cartridge draws wild DVs from two correlated
random bytes, so grass and cave encounters are never shiny or perfect. With the setting on, each
wild encounter gets fully random DVs. Trainer, cable and Transform battles and the old man's
tutorial keep their cartridge DVs. The same saved moment always gives the same DVs, so rewinds
and replays repeat. Gold, Silver and Crystal do not offer it.

## Where your data lives

The [desktop guide](desktop.md#your-files-and-backups) lists platform-specific application folders.
Docker stores the entire library under `/data` inside the container:

- The new quick-start file uses a persistent named volume, normally `pokesim_pokesim-data` when your installation folder is named `pokesim`.
- The original Compose file uses the host folder `./pokesim-app` by default.
- An explicit `DATA_PATH` in `.env` overrides either default.

Keep the registry, installed ROMs, shared assets, all adventures, and interaction records
together. Do not copy one trading participant's saves in isolation. Renaming the Compose
project can select a different volume and make an existing library appear empty.
`docker compose down` keeps the volume. `docker compose down --volumes` deletes it.

## Back up and restore

Open **Settings → Backups** in the Library, create a backup, then download the ZIP to
another location. The application coordinates saving and captures a consistent library.
A backup left only inside the application's data storage does not protect against losing
that storage. Backups contain your private ROMs, saves, and notification settings. Keep
them private and do not attach them to issue reports.

The list shows five backups per page and the total space used. Choose **Delete**
to permanently remove an individual backup after confirmation. Current adventures
and copies already downloaded are unaffected. Backups are not automatically pruned.

To recover one adventure, choose **Load** next to a saved backup, or **Load backup
file** to upload a downloaded ZIP (up to 2 GB). Pick the adventure and name its
restored copy. PokeSim verifies the archive checksums before loading it. The copy
starts stopped with automatic startup and automatic trading disabled. Current
adventures and global settings are preserved. This is useful for inspecting old
progress without replacing your current library. Adventures with no saved data
are not offered for loading.

For a cold copy of a host folder, stop the whole application first, then copy the entire
folder. Pausing an adventure is not equivalent to stopping the manager. For a named volume,
use the Library's downloadable backup instead of looking for a host `./data` folder.

Restore a downloaded ZIP into a new, empty application directory with the application
stopped:

```sh
pokesim restore "/path/to/backup.zip" --data-dir "/path/to/restored-library"
pokesim-desktop --data-dir "/path/to/restored-library"
```

The restore command checks the archive and refuses a nonempty destination. Keep the
original library and backup until the restored adventures, journal, and progress have
been verified. Use the matching application version for the first recovery boot.
For Docker, the same `pokesim restore` command runs in a temporary container with the
backup mounted read-only and a fresh writable destination. See the
[recovery guidance](self-hosting.md#migration-and-recovery).

## Continue in another emulator

Choose **Download Save** on the adventure's Library card. Start the adventure
first if it is stopped. Standalone instances keep **Download .sav** on the Live
page. Export outside battles, dialogue, and trades. If a screen is changing,
wait a moment and retry.
The download contains the current party, PC collection, and cartridge progress.
Load it with the same English ROM in another emulator, using that
emulator's import-save option or matching the save's filename to the ROM.
Gold, Silver and Crystal downloads are a ZIP holding the `.sav` and its `.rtc`
clock file. Put both next to the ROM.

PokeSim opens the native Save menu on a private copy of the current checkpoint,
then boots the resulting 32 KiB cartridge save and verifies Continue restores
the collection and progress. The live adventure keeps playing. The ROM is not
included in the download.

A cartridge save does not contain PokeSim's journal, statistics, marathon records,
trade receipts, or extended play clock. Use a full Library backup to preserve those.
Exported saves are for continuing elsewhere, not for replacing one participant
in a running PokeSim trading library.

## Performance

Each running adventure has its own emulator process. At Max pace, it deliberately
uses available CPU to advance as quickly as possible. Optimizations increase
progress per CPU second, so total CPU utilization can remain high at Max.

PokeSim renders only when a viewer needs a frame or an observation needs a fresh
journal picture. It also encodes live frames only while a viewer is watching.
These savings do not change the configured simulation speed or policy cadence.

## Library resource readings

Each adventure card shows its worker's CPU usage, resident memory, and actual speed. CPU is
measured over the interval between samples. 100% means one fully used logical
core, and a process using several cores can exceed 100%. Memory excludes the
shared library process and is shown in MiB. These are current readings, not
cumulative totals or the whole container's usage.

Actual speed measures simulated seconds per real second over the latest worker
health-check interval, normally about three seconds. For example, 2.3× means
2.3 seconds of game time per real second, even if the selected limit is 4×.
Max has no fixed target. Paused or held workers settle to 0.0×. Cable Club work
runs separately and is not included in this worker reading. Loading a checkpoint
does not count restored frames as new work. Readings older than 15 seconds become
Unavailable, and a restarted worker needs two fresh samples.

The first CPU reading says Measuring until a second sample is available.
Unavailable means the process could not be measured. Stopped adventures say
Not running. Samples are reused for at least two seconds across browser requests.

Recent activity shows the last three observed location changes, with local times.
It is a compact overview, not the full journal or a raw diagnostic log. Every
managed simulation page links back to the Library through the PokeSim logo.
The adventure selector switches between games without returning to the Library.

## Trade preparation limit

Before an automatic trade, both games walk to a Pokémon Center's Cable Club. The original gives
up after 15 real minutes in the Library and 30 in each game, whatever the game speed, so a game at
8x that cannot find its way paces for a long time. Set `TRADE_PREPARE_SECONDS` to the game time
that walk may take at 1x. Each game gets that divided by its speed, the Library uses the slower
game's, an unlimited-speed game counts as 16x and no limit drops under a minute. For example, 600
gives 10 minutes at 1x, 2 minutes 30 seconds at 4x and 1 minute at 16x. A trade that runs out of
time is called off safely and both games carry on with their own Pokémon.

## Dashboard stats

`GET /api/v1/stats` returns read-only numbers for a home dashboard such as Homepage,
Home Assistant or your own page. It holds library totals (`running`, `adventures`,
`badges`, `owned`, `hall_of_fame`, `playtime_seconds`) and a `list` with one entry per
adventure: game, state, speed, trainer, badges out of `badge_total`, Pokédex owned and seen
out of `dex_total`, Hall of Fame count, money, play time, location and party (species,
nickname, level, Pokédex number, shiny). `GET /api/v1/stats/<adventure id>` returns one entry on its own.

The numbers come from the reports each running game already sends the Library, so reading
them costs nothing. A stopped adventure keeps the numbers from its last report, and an
adventure that has never run reports `null`. Archived adventures are left out.

Like every Library request, these need the address in `PUBLIC_URL`. A dashboard on another
machine should call that address, for example `http://pokesim.lan/api/v1/stats`, not the
container IP. A Homepage card:

```yaml
- PokeSim:
    href: http://pokesim.lan
    widget:
      type: customapi
      url: http://pokesim.lan/api/v1/stats
      mappings:
        - field: running
          label: Running
        - field: badges
          label: Badges
        - field: owned
          label: Caught
```

## TV view

Open `/tv` (or **TV view** in the Library) for every running adventure on one screen, made
for a wall display or a small kiosk. Each tile shows the live game with its name, trainer,
speed, location, play time, badges, Pokédex count and party. The grid picks the column count
that gives every screen the most room, and the mouse pointer hides after three seconds.

Options go in the address, for example `/tv?ids=abc,def&info=0`:

| Option | Effect |
| --- | --- |
| `ids=a,b` | Only these adventures, in this order |
| `all=1` | Also show stopped adventures, with their last numbers |
| `stream=0` | Still frames instead of live video, for a slow kiosk or network |
| `fps=30` | Frames per second. Live video 1 to 60, defaulting to the server's `STREAM_FPS`. Still frames 0.2 to 10, default 2 |
| `info=0` | Game screens only |
| `bare=1` | Hide the top bar too |

Live video for every game arrives on one connection, `/api/v1/tv/stream`, where the Library
reads each game's stream and passes on the newest frame of each. Browsers keep only about six
connections open to one server, so one stream per tile would leave none for party sprites and
stats once six games are running. For fast games, raise `STREAM_FPS` in the environment (up to
60) so 4x and 8x stay readable. In this fork every game without its own `stream_fps` setting
follows it. Six games at 60 send about 1 MB/s, so a weak Wi-Fi link may do better at 30. On a Raspberry Pi or other low-power kiosk, `stream=0&fps=1`
keeps the load light.

## Watchdog

The Library checks every adventure once a minute and tells you about problems an adventure
cannot fix by itself. It sends through your existing notification destinations under
Stuck or needs attention, and lists current problems above the adventure cards.

| Problem | Default limit |
| --- | --- |
| An adventure that should be running is not, and you did not stop it | 2 minutes |
| An adventure is stuck in one place | 15 minutes |
| An adventure keeps playing but nothing new happens, such as a loop between two spots | 60 minutes |
| A trade waits in preparing or connecting | 10 minutes |
| Trades fail for the same reason | 3 times in 2 hours |
| PokeSim or a worker logs an unexpected error | Once per error per hour |

New Pokédex entries, badges, events, League wins and maps not visited recently count as
progress. Walking around does not. A help request from Gold, Silver or Crystal appears in
the list only, since that adventure already sends its own Stuck notification.

Each problem sends one alert when it starts and one short note when it clears. The same
problem stays quiet for an hour after its last alert. For five minutes after a restart,
problems are noted but not sent, so restarting does not repeat old alerts.

Turn the watchdog off with `POKESIM_WATCHDOG=0`, or with
`PATCH /api/v1/watchdog` and `{"enabled": false}`, which is saved and wins over the
environment. Change a limit with `POKESIM_WATCHDOG_<NAME>` in minutes, using the names
`DOWN`, `STUCK`, `NO_PROGRESS`, `TRADE_WAITING`, `FAILURE_WINDOW`, `ERROR_QUIET`,
`COOLDOWN`, `GRACE` and `INTERVAL`. `POKESIM_WATCHDOG_FAILURE_REPEATS` is a count.

## Update and roll back

Create and download a backup, then stop the app. For a native installation, follow
[desktop updates](desktop.md#update-or-remove). For Docker, follow
[container updates](self-hosting.md#back-up-update-and-remove). Preserve your selected data
mount, project name, and `.env` settings. Release image tags and wheel URLs pin versions,
so pulling or upgrading the same URL does not automatically select the newest release.

A rollback may require both the previous application version and its matching backup.
Do not run an older version against a library modified by a newer version unless that
release explicitly supports it. Restore into a separate location to preserve current progress.

Gold, Silver and Crystal adventures need 0.5.0 or later. Starting one on 0.4.x fails with
"Worker exited before becoming ready" and "Unknown settings: celebi_event", because 0.4.x does not know
Generation II. Older releases cannot be taught a clearer message from this side, so stop those adventures
before rolling back and use 0.5.0 or later to open them. Generation I adventures roll back normally once
**Fair wild DVs** is turned off.

## Health, storage, and recovery

The manager's `/health/ready` endpoint reports readiness. Docker checks it automatically.
Inspect individual adventure failures in the Library and startup failures in the container
logs. Docker marks failed health checks as unhealthy, but that alone does not restart a
still-running container.

Check free disk space when saving or setup fails. Keep the complete application and
interaction records together after an interrupted trade, then restart to let the manager
finish its recorded decision. Never bypass a committed trade by restoring only one game.

Container logs rotate at three files of 10 MB each. Backups and adventure history can
still consume disk space, so keep an eye on storage and move downloaded backups to your
normal backup destination. Phone notifications are configured in the Library and are
included in full backups. Disable them when running a test copy to avoid duplicate alerts.
