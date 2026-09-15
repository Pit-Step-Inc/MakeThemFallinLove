# MAKE THEM FALL (in love)

## Play

You can play the project here:

- Vercel: https://make-them-fall-in-love001.vercel.app
- Render: https://make-them-fall.onrender.com

## How To Play / 操作方法

1. 最初に言語を選択します。

![Language select](docs/play-guide/001_RE.png)

2. 自分が Host になるか、共有されたルームコードを入力してゲームに参加します。

![Host or join](docs/play-guide/002_RE.png)

![Room code](docs/play-guide/003_RE.png)

3. Martin と Catherine のデートが始まります。

![Opening scene](docs/play-guide/004_RE.png)

4. Prompt 入力画面になったら、Martin にしてほしい行動やアドバイスを入力します。入力した Prompt は画面上部に表示されます。

![Prompt input](docs/play-guide/005_RE.png)

![Submitted prompts](docs/play-guide/006_RE.png)

5. 良いと思った Prompt にいいねします。もっとも多くいいねされた Prompt が採用されます。

![Like prompts](docs/play-guide/007_RE.png)

6. 採用された Prompt をもとに、AI が次のストーリーを生成します。

![Selected prompt](docs/play-guide/008_RE.png)

![Generated story](docs/play-guide/009_RE.png)

7. ストーリーの内容によって、Catherine の親密度が変化します。

![Affection change](docs/play-guide/010_RE.png)

8. デート中には、ランダムイベントが発生することがあります。

![Random event](docs/play-guide/011_RE.png)

9. 最終的なゴールは、Catherine の親密度を 100 にすることです。親密度が 100 になると特殊な演出を見ることができます。100 に届くまで、何度もプレイして Martin の恋を成功させてください。

![Goal](docs/play-guide/012_RE.png)

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
- Backend: Python 3.12 server via `tools/serve.py`.
- Room state: in-process memory for a single Render instance.
- Generated images: saved to disk under the server-managed asset flow.
- Deployment: `main` is configured for Render; the Vercel version lives on the `vercel` branch.

## Tools And Assets

- DotGothic16 font: SIL Open Font License 1.1.
- Blender: used for sprite and animation asset production.
- OpenMusic: used to generate BGM/audio assets.
- OpenAI: used for story, dialogue, visual generation, and AI-assisted development.
- Original project assets: character images, UI, backgrounds, sound effects, scripts, and game code were created for this project unless otherwise noted.
