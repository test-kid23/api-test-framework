/**
 * i18next 国际化配置.
 *
 * 当前仅支持中文，英文已关闭。
 * 如需恢复多语言支持，取消注释 LanguageDetector 和检测配置即可。
 */
import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import zhCN from "./locales/zh-CN.json";

const resources = {
  "zh-CN": { translation: zhCN },
};

i18n
  .use(initReactI18next)
  .init({
    resources,
    lng: "zh-CN",
    fallbackLng: "zh-CN",
    debug: false,
    interpolation: {
      escapeValue: false, // React 已内置 XSS 防护
    },
  });

export default i18n;
