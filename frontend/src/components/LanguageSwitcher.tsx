/**
 * 语言切换组件.
 *
 * 提供中英文切换的下拉菜单，语言偏好存储到 localStorage.
 */
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Languages } from "lucide-react";

const LANGUAGES = [
  { code: "zh-CN", label: "中文" },
  { code: "en-US", label: "English" },
] as const;

export function LanguageSwitcher() {
  const { i18n } = useTranslation();

  const currentLang = i18n.language?.startsWith("en") ? "en-US" : "zh-CN";

  const handleChange = (lang: string) => {
    i18n.changeLanguage(lang);
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" title="语言 / Language">
          <Languages className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-32">
        {LANGUAGES.map((lang) => (
          <DropdownMenuItem
            key={lang.code}
            onClick={() => handleChange(lang.code)}
            className={currentLang === lang.code ? "font-semibold" : ""}
          >
            {lang.label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
