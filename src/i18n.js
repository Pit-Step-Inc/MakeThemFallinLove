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
  },
  ja: {
    titleHint:    "← → で選択・Enter で決定",
    yourName:     "あなたのなまえ",
    namePlaceholder: "ニックネーム（7文字まで）",
    next:         "つぎへ",
    back:         "← もどる",
    nicknameHint: "なまえを入れて「つぎへ」",
    notImplemented: (name) => `ようこそ ${name} — 次のシーンは未実装です`,
  },
};

/** @param {"en"|"ja"} lang */
export function t(lang) {
  return STRINGS[lang] ?? STRINGS.en;
}
