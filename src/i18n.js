/**
 * 画面に出す文言
 *
 * タイトルで選んだ言語がそのまま以降のシーンに引き継がれる。
 * 新しいシーンを足すときはここにキーを増やす。
 */

export const STRINGS = {
  en: {
    titleHint:    "← → to choose ・ Enter to start",
    yourName:     "Your Name",
    namePlaceholder: "Nickname (up to 7 characters)",
    next:         "Next",
    back:         "← Back",
    nicknameHint: "Enter your name, then press Next",
    notImplemented: (name) => `Welcome, ${name} — the next scene is not implemented yet`,
    day:          (n) => `Day ${n}`,
    dayHint:      "Click to continue",
    // 冒頭の会話。日ごとに1本で、添字は day - 1。
    // 背景は src/main.js の OPENING_BACKDROPS と同じ並び
    openingScripts: [
      [
        { who: "martin",    text: "I can't believe I'm going on\na date with someone like her..." },
        { who: "martin",    text: "She's late, though...\nFifteen minutes past our time..." },
        { who: "catherine", text: "Sorry to keep you waiting!" },
        { who: "martin",    text: "H-hey there..." },
        { who: "catherine", text: "So? What do we do now?" },
      ],
      [
        { who: "martin",    text: "I hope she's on time today..." },
        { who: "catherine", text: "Sorry to keep you waiting!" },
        { who: "martin",    text: "O-only five minutes today." },
        { who: "catherine", text: "You counted?\nSo you really did wait for me." },
        { who: "martin",    text: "Y-yeah. So, what do we do now?" },
      ],
      [
        { who: "martin",    text: "Three dates with her...\nI still can't believe it." },
        { who: "martin",    text: "Maybe she's getting a little\nused to me by now..." },
        { who: "catherine", text: "Oh, you're here already." },
        { who: "martin",    text: "Yeah. Same as always." },
        { who: "catherine", text: "Not everyone's as free as you." },
        { who: "catherine", text: "So, what do we do today?" },
      ],
    ],
    promptLabel:       "What happens next?",
    promptPlaceholder: "Who does what and where, in 50 characters",
    promptLike:        "Like this prompt",
    promptSent:        "Sent - now vote for the others",
    promptClosed:      "Time is up",
    nextUp:            "What happens next",
    roomHeading:       "Play together",
    beHost:            "Host a room",
    roomOr:            "or",
    codePlaceholder:   "Room code",
    joinRoom:          "Join",
    roomHint:          "Host a room, or type the code you were given",
    roomNotFound:      "No room with that code",
    roomJoinFailed:    "Could not join - try again",
    roomCode:          "CODE",
    copyCode:          "Copy the room code",
    codeCopied:        "COPIED",
    codeCopyFailed:    "COPY FAILED",
    waitingForPlayers: "Waiting for everyone",
    startNow:          "Start now",
    generating:        "Writing what happens next...",
    generateFailed:    "Could not reach the story service",
    affinityUp:        (n) => `Catherine +${n}`,
    affinityDown:      (n) => `Catherine -${n}`,
    playerJoined:      (n) => `${n} joined`,
    playerLeft:        (n) => `${n} left`,
    topPlayers:        "TOP PLAYERS",
    theEnd:            "The End",
    finalAffinity:     "Final Affinity",
    backToTitle:       "Back to Title",
    eventHeading:      "EVENT!",
    // AI が考えたお題の差出人。渦の画面の札に出る
    aiAuthor:          "AI",
    yearsLater:        (n) => `${n} Years Later`,
    notOverTitle:      "The story is not over yet...",
    notOverBody:       "Reach 100 affinity and you might see a new story.",
  },
  ja: {
    titleHint:    "← → で選択・Enter で決定",
    yourName:     "あなたのなまえ",
    namePlaceholder: "ニックネーム（7文字まで）",
    next:         "つぎへ",
    back:         "← もどる",
    nicknameHint: "なまえを入れて「つぎへ」",
    notImplemented: (name) => `ようこそ ${name} — 次のシーンは未実装です`,
    day:          (n) => `${n}日目`,
    dayHint:      "クリックですすむ",
    // 台本。改行は明示する。自動折り返しに任せると「するこ／と」の
    // ように語の途中で割れる（.bubble-text は white-space: pre-line）
    // 冒頭の会話。日ごとに1本で、添字は day - 1。
    // 背景は src/main.js の OPENING_BACKDROPS と同じ並び
    openingScripts: [
      [
        { who: "martin",    text: "こんな僕があんな美女とデートすること\nになるなんて..." },
        { who: "martin",    text: "それにしても遅いな...\n集合時間から15分もたっている..." },
        { who: "catherine", text: "おまたせー" },
        { who: "martin",    text: "や、やぁ" },
        { who: "catherine", text: "で？これからどうするの？" },
      ],
      [
        { who: "martin",    text: "今日は遅刻しないといいけど..." },
        { who: "catherine", text: "おまたせー" },
        { who: "martin",    text: "き、今日は5分だけだね" },
        { who: "catherine", text: "細かっ。ちゃんと待ってたんだ？" },
        { who: "martin",    text: "う、うん。これからどうする？" },
      ],
      [
        { who: "martin",    text: "まさか3回もデートできるなんて..." },
        { who: "martin",    text: "ちょっとは僕にも\n慣れてくれたのかな..." },
        { who: "catherine", text: "おー、もう来てんじゃん" },
        { who: "martin",    text: "うん。いつもどおりだね。" },
        { who: "catherine", text: "私はあんたみたいに暇じゃないの" },
        { who: "catherine", text: "今日はどうする？" },
      ],
    ],
    promptLabel:       "次の展開は？",
    promptPlaceholder: "どこで誰がなにをしたかを40文字以内で",
    promptLike:        "この Prompt に いいね",
    promptSent:        "送信しました。ほかの人にいいねを",
    promptClosed:      "時間切れです",
    nextUp:            "次の展開",
    roomHeading:       "みんなで遊ぶ",
    beHost:            "ホストになる",
    roomOr:            "または",
    codePlaceholder:   "ルームコード",
    joinRoom:          "参加",
    roomHint:          "ホストになるか、教わったコードを入れてください",
    roomNotFound:      "そのコードの部屋がありません",
    roomJoinFailed:    "入れませんでした。もう一度",
    roomCode:          "コード",
    copyCode:          "ルームコードをコピー",
    codeCopied:        "コピーしました",
    codeCopyFailed:    "コピーできません",
    waitingForPlayers: "みんなを待っています",
    startNow:          "先に始める",
    generating:        "次の展開を書いています…",
    generateFailed:    "次の展開を作れませんでした",
    affinityUp:        (n) => `親密度 +${n}`,
    affinityDown:      (n) => `親密度 -${n}`,
    playerJoined:      (n) => `${n} が参加しました`,
    playerLeft:        (n) => `${n} が退出しました`,
    // 参照画像（Ending_001 / 002）が英語表記なので、日本語でもそのまま出す
    topPlayers:        "TOP PLAYERS",
    theEnd:            "The End",
    finalAffinity:     "最終親密度",
    backToTitle:       "タイトルへ",
    eventHeading:      "イベント発生",
    aiAuthor:          "AI",
    yearsLater:        (n) => `${n}年後`,
    // 改行は明示する。自動折り返しに任せると「ストーリ／ー」のように
    // 語の途中で割れる（.not-over__title / __body は white-space: pre-line）
    notOverTitle:      "物語は、\nまだ終わっていない。。。",
    notOverBody:       "親密度が100になると、\n新しいストーリーが見られるかも？",
  },
};

/** @param {"en"|"ja"} lang */
export function t(lang) {
  return STRINGS[lang] ?? STRINGS.en;
}
