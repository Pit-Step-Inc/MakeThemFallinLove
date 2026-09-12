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
    openingScript: [
      { who: "martin",    text: "I can't believe I'm going on\na date with someone like her..." },
      { who: "martin",    text: "She's late, though...\nFifteen minutes past our time..." },
      { who: "catherine", text: "Sorry to keep you waiting!" },
      { who: "martin",    text: "H-hey there..." },
      { who: "catherine", text: "So? What do we do now?" },
    ],
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
    openingScript: [
      { who: "martin",    text: "こんな僕があんな美女とデートすること\nになるなんて..." },
      { who: "martin",    text: "それにしても遅いな...\n集合時間から15分もたっている..." },
      { who: "catherine", text: "おまたせー" },
      { who: "martin",    text: "や、やぁ" },
      { who: "catherine", text: "で？これからどうするの？" },
    ],
  },
};

/** @param {"en"|"ja"} lang */
export function t(lang) {
  return STRINGS[lang] ?? STRINGS.en;
}
