MEDIA TO CAPCUT TIMELINE
=======================

WHAT THESE FILES ARE
--------------------

The shared implementation is MediaToCapcut.py. It is used by both native entry
points:

  Media to Capcut Timeline by Banong Gang.command
  Media to Capcut Timeline by Banong Gang.bat

The .command file is the macOS entry point. The .bat file is the native Windows
entry point and does not require Git Bash or WSL. No third-party Python packages
are required.

It creates a new CapCut draft from a folder of images and videos, registers that
draft in CapCut's project list, and can open CapCut afterward.

It does not export an MP4. After opening the generated project, use CapCut to
review it and export it normally.

On macOS, double-click Media to Capcut Timeline by Banong Gang.command in
Finder. On Windows, double-click Media to Capcut Timeline by Banong Gang.bat.


SCREENSHOTS
----------

Both screenshots show the terminal window while the app runs: the prompts for
the media folder, duration, audio, project name, ratio, and frame rate, followed
by the summary and the confirmation to create the CapCut project.

  Screenshot 1.png
  Screenshot 2.png

The same two images are shown near the top of README.md, which GitHub renders
with the captions used there.


WINDOWS REQUIREMENTS
--------------------

The Windows launcher looks for Python 3 through `py -3`, then `python`. It also
requires ffmpeg.exe and ffprobe.exe for reliable video metadata, audio duration,
and cover generation. When one of them is missing, the .bat offers to download it:
Python is installed silently for the current user, and ffmpeg.exe and ffprobe.exe
are saved in the same folder as the .bat file, which is added to PATH for the
run. Answer N to skip the download and read the manual instructions instead. Set
MEDIATOCAPCUT_NO_SETUP=1 to disable the download prompts. The manual download
page is
https://github.com/descriptinc/ffmpeg-ffprobe-static/releases/tag/b6.1.2-rc.1
Each file is about 120 MB. CapCut must be installed and contain an empty draft
template.

The shared core checks the Windows LocalAppData and AppData locations for the
CapCut draft root. Use `--draft-root PATH` or the `CAPCUT_DRAFT_ROOT`
environment variable when CapCut stores drafts elsewhere. A successful default
Windows console run exits without the old Enter-to-close prompt; use
`--keep-open` to retain it. The .bat launcher pauses when the program reports an
error.


WHAT IT CREATES
---------------

For each image or video, the command creates one continuous segment on a single
video track. There are no gaps between media clips. Videos keep their embedded
audio when the source contains an audio stream.

It does not add:

- Transitions
- Zooms or pans
- Text
- Stickers
- Color effects
- Background music unless you provide an audio file

The default project settings are:

- Canvas: 16:9 landscape, 1920 x 1080
- Frame rate: 30 fps
- Placement: native 100% scale (no automatic enlargement)
- Media order: filename order
- Project name: current month and day, such as 0925

With the default native placement, each media clip is centered at its original
1.0 scale. If the source is smaller than the canvas, black borders may appear;
if it is larger, the parts outside the canvas are cropped. Use --fill to enlarge
media until it covers the frame, or --fit to enlarge it only as needed to fit
inside the frame.

Video clips are trimmed from source time 0. In timestamp mode, each video ends
at the next media timestamp, and the last video uses the requested final clip
length. If a video is shorter than its assigned slot, the command stops with an
error before changing CapCut projects.


HOW MEDIA TIMING WORKS
----------------------

The command automatically chooses one of two timing modes.

1. TIMESTAMP FILENAME MODE
--------------------------

This mode is selected when every media filename contains a valid timestamp.
Image and video files can be mixed in the same folder.

Examples of a mixed-media filename sequence are:

  0-00.png
  0-09.jpg
  0-18.mp4
  0-28.mov
  0-37.png
  0-47.jpg
  0-57.mp4

The first component may use one or two digits, so names such as 0-00.jpeg,
0-06.jpeg, and 0-11.jpeg are interpreted as 00:00, 00:06, and 00:11.

This example creates approximately these media durations:

  Media 1:  9 seconds
  Media 2:  9 seconds
  Media 3: 10 seconds
  Media 4:  9 seconds
  Media 5: 10 seconds
  Media 6: 10 seconds
  Media 7:  5 seconds
  Total:   62 seconds

The media are sorted by their parsed timestamps. Each video starts at source
time 0 and is cut at the next timestamp. The last media clip remains for 5
seconds by default. If an audio file is longer, the project extends to the
audio duration.

Other accepted timestamp examples are:

  00-09.500.png
  01-02-03.mp4
  83.5.mov

For 83.5.mov, the value is interpreted as 83.5 seconds.

Every image or video filename must have a valid timestamp in timestamp mode.
If even one filename is not valid, automatic mode falls back to even spacing and
prints a warning when some filenames look like timestamps.


2. EVEN-SPACING MODE
--------------------

This mode is used when the media filenames are ordinary names such as:

  01.png
  02.jpg
  03.mp4
  04.mov
  05.png
  06.jpg
  07.mp4

The command divides the requested total duration equally between the media.

For seven media files and a 62-second duration:

  62 seconds / 7 media = approximately 8.857 seconds per clip

The boundaries are adjusted slightly so they align with the selected frame
rate. The total remains exactly 62 seconds.

Media are ordered naturally, so 2.mp4 comes before 10.png. Videos in even
spacing mode are also trimmed to their assigned slot and must be at least that
long.


AUDIO
-----

Audio is optional. Leave the audio prompt blank to create a project without
an external audio track. Audio already embedded in a video is retained when
present; an optional external audio file is added as a separate track, so both
can play.

The command reads the external audio duration automatically.

In even-spacing mode:

- The audio duration becomes the project duration.

In timestamp mode:

- The project ends after the last media clip, unless the external audio is longer.
- If the external audio is longer, the project is extended to its duration.

Supported audio extensions are:

  .wav
  .mp3
  .m4a
  .aac
  .flac
  .ogg


HOW TO USE IT
-------------

1. Quit CapCut completely.

   Press Command-Q in CapCut. The command refuses to change CapCut projects
   while CapCut is still running.

2. Put the intended images and videos in one folder.

   The command uses the entire folder rather than opening a seven-file picker.
   For predictable results, use only the media that belong in the timeline.

3. Double-click the entry point for your platform:

   macOS: Media to Capcut Timeline by Banong Gang.command
   Windows: Media to Capcut Timeline by Banong Gang.bat

4. Review the detected asset folder.

   Press Enter to accept it, or drag the correct folder into the Terminal or
   Command Prompt window and press Enter.

5. Review the remaining settings.

   Typical prompts are:

   Assets folder
   Target length in seconds or M:SS
   Last clip length in seconds
   Optional audio file
   CapCut project name
   Ratio
   Frame rate

    The target-length prompt is shown for even-spacing mode. Timestamp mode uses
    the times encoded in the image and video filenames and asks for the last
    clip length instead.

6. Review the summary.

   It shows the project name, image/video counts, timing mode, total length,
   average media duration, ratio, frame rate, placement, audio, and template.

7. Type Y when asked:

   Create the CapCut project?

8. Choose whether to open CapCut.

9. On macOS, the Terminal window closes automatically after a successful run.
   On Windows, a successful default console run exits without an extra Enter
   prompt. Use --keep-open when you want to keep the window open for inspection.


MEDIA FORMATS
-------------

Supported image extensions are:

  .jpg
  .jpeg
  .png
  .webp
  .bmp

Supported video extensions are:

  .mp4
  .mov

For media metadata and covers, the shared core uses ffprobe and ffmpeg when
available, with macOS Spotlight and Quick Look as macOS fallbacks. If the
required metadata cannot be read, the command reports an error before creating
a draft.

Image and video extensions are recognized case-insensitively. Some CapCut
versions may not display WebP images correctly.


SAFETY AND BACKUPS
------------------

- The command does not edit the original images or videos.
- Existing projects with the same name are backed up before replacement.
- Replaced projects are moved into a hidden backup folder named .banong-backup.
- CapCut's root project index is backed up as:

  root_meta_info.json.banong-backup

- Generated files are first assembled in a temporary project folder.
- Generated media are stored in the project's banong-media folder.
- If generation fails, the command restores the previous root index and
  restores any project that was moved to the backup folder.
- The command creates a draft project; it does not modify an existing draft in
  place.


EMPTY TEMPLATE REQUIREMENT
--------------------------

The command searches CapCut's draft folder for an empty project to use as a
CapCut-compatible template.

If no empty project exists:

1. Open CapCut.
2. Create one new empty project.
3. Quit CapCut.
4. Run the command again.


PREVIEW WITHOUT CREATING A PROJECT
----------------------------------

To review the settings without changing CapCut, open Terminal in this folder
and run:

  "./Media to Capcut Timeline by Banong Gang.command" --dry-run

The dry run reads the media and calculates the timeline but does not create or
modify a CapCut project.


NATIVE, FIT, OR FILL PLACEMENT
------------------------------

The default placement is native 100% scale. It does not enlarge or shrink the
source. To show the entire image or video frame with possible black borders,
run:

  "./Media to Capcut Timeline by Banong Gang.command" --fit

To enlarge media until it covers the entire frame and crop any excess, run:

  "./Media to Capcut Timeline by Banong Gang.command" --fill

Native, fit, and fill are centered. Native keeps the source at 1.0 scale; fit
keeps the whole source visible; fill crops the source.


USEFUL COMMAND-LINE OPTIONS
---------------------------

  --assets PATH
      Use a specific image/video folder.

  --timing auto|filename|list|even
      Choose the timing method.

  --duration SECONDS
      Set the even-spacing duration, such as 62 or 1:02.

  --last-duration SECONDS
      Set the final media duration in timestamp mode.

  --audio PATH
      Add an audio file.

  --ratio 16:9|9:16|1:1
      Select the canvas ratio.

  --fps 24|25|30|50|60
      Select the frame rate.

  --fit
      Keep the whole image or video frame visible, scaling it to fit.

  --fill
      Enlarge media to cover the frame and crop any excess.

  --name NAME
      Set the CapCut project name.

  --dry-run
      Preview without changing CapCut.

   --no-launch
       Create the draft without opening CapCut.

   --no-pause
       Do not show the close prompt after a successful run.

   --keep-open
       Keep the Terminal or Windows console window open after a successful run.

   --self-test
       Run the built-in timing and JSON checks.


Examples:

  "./Media to Capcut Timeline by Banong Gang.command" --assets "/path/to/media" --duration 62

  "./Media to Capcut Timeline by Banong Gang.command" --ratio 9:16 --fps 30

  "./Media to Capcut Timeline by Banong Gang.command" --dry-run --no-launch
