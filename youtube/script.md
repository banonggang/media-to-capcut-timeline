# Media to CapCut Timeline — YouTube Script

Target length: 3:00-3:35. Screen recording with light voiceover. No face needed.
Terminology on screen: the app is "Media to CapCut Timeline by Banong Gang", the
generated result is a "CapCut draft project", and CapCut itself is used to export
the final MP4.

## 0:00-0:08 HOOK

- Visual: folder of mixed clips (images + videos) on the left, an arrow, a CapCut
  timeline on the right. Hard cut, no intro.
- Text on screen: "One folder in. A full CapCut timeline out."
- Voiceover: "I have a folder of twenty images and videos. I do not want to drag
  them into CapCut one by one, so I made this."

## 0:08-0:25 THE PROBLEM

- Visual: a CapCut project with 40 clips in the timeline, someone scrubbing back and
  forth.
- Voiceover: "Every short-form edit starts the same way: rename files, sort them,
  drag each one in, fix the length, and hope the timing matches what you planned.
  That is the boring part. This tool removes it."

## 0:25-0:45 WHAT IT DOES (three beats, one line each)

- Visual: title cards, one per line.
  1. "Reads a folder of images and videos, mixed together."
  2. "Builds the timeline timing from the filenames or an even split."
  3. "Creates a real CapCut project, already registered in CapCut."
- Voiceover: "Drop a folder in. It reads every image and video, decides the timing,
  and generates a real CapCut project that shows up in your project list. It does
  not export an MP4, you finish and export in CapCut like you always do."

## 0:45-1:05 GETTING IT

- Visual: screen recording of the GitHub repo page, README visible.
- Voiceover: "It is on GitHub, it is free, and there is one download. On macOS,
  double-click the .command file. On Windows, double-click the .bat file. No
  terminal commands, no WSL. The first time it runs, it offers to install Python,
  ffmpeg, and ffprobe for you, so there is nothing else to set up."

## 1:05-2:20 THE SCREEN WALKTHROUGH (the core of the video)

- Double-click the launcher. Terminal opens.
- First prompt is the media folder. Show dragging the folder into the Terminal and
  pressing Enter.
- Show the remaining prompts in sequence, no need to read them all out loud:
  target length, last clip length, optional audio file, project name, ratio, frame
  rate.
- Voiceover: "The prompts are short. Pick a length for an even split, or leave the
  timing to the filenames. Add an audio track if you want one, and choose 16:9,
  9:16, or square."
- Show the summary screen. Point at the counts, total length, average clip length,
  ratio, frame rate, and placement.
- Voiceover: "Before anything changes, it prints exactly what it is about to do.
  Media count, total length, average clip length, canvas, frame rate, placement.
  If something is wrong, Ctrl-C and fix it, nothing is written yet."
- Type Y.
- Voiceover: "Y creates the project. It is assembled in a temporary folder first,
  then moved into CapCut's draft list, and the old version is backed up."
- CapCut opens. Scrub the timeline, show images and videos in sequence, show the
  audio waveform.
- Voiceover: "That is it. Images, videos, and audio in one continuous track, ready
  to edit."

## 2:20-2:50 THE TWO THINGS PEOPLE ASK ABOUT

- Visual: side-by-side, native 100% scale on the left, a frame-filling version on
  the right.
- Voiceover: "Two quick answers. Scale is native 100% by default, so nothing is
  secretly cropped or blown up. If you want to fill the frame, run it with --fill,
  or --fit to keep the whole image visible. And timing: rename your files
  0-00.png, 0-09.jpg, 0-18.mp4 and it uses those timestamps exactly. Ordinary
  names like 01.png, 02.jpg and it splits the total duration evenly."

## 2:50-3:10 SAFETY

- Visual: terminal showing the confirmation, then the app in CapCut; cut to the
  README safety section.
- Voiceover: "It refuses to touch CapCut while CapCut is running, so quit CapCut
  first. Existing projects with the same name are backed up, generated media go
  into a project folder, and if anything fails it restores the previous state. And
  --dry-run lets you check the whole plan without creating anything."

## 3:10-3:30 CLOSE

- Visual: GitHub repo page, then the app title card.
- Voiceover: "If that saves you the boring part, clone it, star it, and tell me in
  the comments what you would want it to do next. Link is in the description."
- Text on screen: repo URL, "Mac + Windows", "Free and open source".

## 45-SECOND SHORTS CUT

Beat 1 (0-4): folder of clips, "One folder in."
Beat 2 (4-12): double-click, prompts, Y, fast cuts at 2x speed.
Beat 3 (12-20): CapCut opens with the finished timeline.
Beat 4 (20-30): "Native 100% scale. Timestamps or even split. Mac and Windows."
Beat 5 (30-45): repo URL, "Free on GitHub", star comment prompt.

## FILMING NOTES

- Record the screen at 1920x1080, crop to 16:9, no cursor smoothing plugins.
- Show the terminal in a readable font size; the prompts are the story.
- Do not record any personal CapCut project names or media. Use a folder of test
  clips.
- Keep every gap under a second in the walkthrough. This video lives or dies on the
  1:05-2:20 section.
- Music: nothing loud under the voiceover. Royalty-free only.
- Do not claim the tool is official. Add the disclaimer from the description.
