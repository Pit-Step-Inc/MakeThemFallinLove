# MAKE THEM FALL (in love)

## Play

You can play the project here:

- Vercel: https://make-them-fall-in-love001.vercel.app
- Render: https://make-them-fall.onrender.com

## Game Overview

What if you could step into a dating reality show and change what happens next? MAKE THEM FALL (in love) is an AI-powered multiplayer dating simulation where players influence Martin, an awkward and inexperienced guy, as he tries to win - or completely ruin - his date with Catherine.

It is designed for casual gamers, streamers, and online communities who want to shape a story together. Through Twitch, YouTube, TikTok, and other social platforms, anyone can join simply by submitting ideas or voting on what Martin should do next.

The top-voted choice becomes part of the story. AI then generates the next scene in real time - including background visuals, character reactions, dialogue, and the consequences that follow. Instead of following a fixed narrative, every playthrough evolves through the collective decisions of the audience.

Our goal is to create a Forever Game: an endlessly evolving "Unreality Show" where AI and the community continuously generate new drama, relationships, and stories.

## How It Works

- Players join a shared room and submit ideas for Martin's next move.
- The audience votes, and the top-voted idea becomes the next story prompt.
- AI generates the following scene, including dialogue, background art, relationship changes, and BGM selection.
- The story continues until Martin and Catherine either reach a happy ending or the date falls apart.

## Tech Stack

- Client: vanilla ES modules, HTML, CSS, Canvas, and WebAudio.
- Backend: Python 3.12 Vercel Functions via `api/index.py`.
- Room state: Redis on Vercel Marketplace when configured, with an in-memory fallback for local or Render-style environments.
- Generated images: Vercel Blob when configured, with a disk fallback for non-Vercel environments.
- Deployment: this branch is configured for Vercel.

## Tools And Assets

- DotGothic16 font: SIL Open Font License 1.1.
- Blender: used for sprite and animation asset production.
- OpenMusic: used to generate BGM/audio assets.
- OpenAI: used for story, dialogue, visual generation, and AI-assisted development.
- Original project assets: character images, UI, backgrounds, sound effects, scripts, and game code were created for this project unless otherwise noted.
