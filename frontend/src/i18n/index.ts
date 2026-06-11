/**
 * i18next 国际化配置.
 *
 * 支持中英文切换，语言偏好存储到 localStorage.
 */
import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import LanguageDetector from "i18next-browser-languagedetector";

import zhCN from "./locales/zh-CN.json";
import enUS from "./locales/en-US.json";

const resources = {
  "zh-CN": { translation: zhCN },
  "en-US": { translation: enUS },
};

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources,
    fallbackLng: "zh-CN",
    debug: false,
    interpolation: {
      escapeValue: false, // React 已内置 XSS 防护
    },
    detection: {
      order: ["localStorage", "navigator"],
      caches: ["localStorage"],
      lookupLocalStorage: "autotest-lang",
    },
  });

export default i18n;
