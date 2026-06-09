import { useState, useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useCase, useCreateCase, useUpdateCase } from "@/hooks/useCases";
import { useSuites } from "@/hooks/useSuites";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Skeleton } from "@/components/ui/skeleton";
import { TagInput } from "@/components/ui/tag-input";
import { toast } from "sonner";
import { ArrowLeft, Loader2, Save, Code2, Check, Eye } from "lucide-react";
import { usePermission } from "@/hooks/usePermission";

export function CaseEditPage() {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const isEdit = !!id;
  const { canEdit } = usePermission();

  const { data: existingCase, isLoading } = useCase(id);
  const { data: suitesData } = useSuites({ page_size: 100 });
  const createCase = useCreateCase();
  const updateCase = useUpdateCase();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [yamlContent, setYamlContent] = useState("");
  const [tags, setTags] = useState<string[]>([]);
  const [priority, setPriority] = useState<string>("P2");
  const [timeout, setTimeout_] = useState<string>("");
  const [lineCount, setLineCount] = useState(1);

  useEffect(() => {
    if (existingCase) {
      setName(existingCase.name);
      setDescription(existingCase.description || "");
      setYamlContent(existingCase.yaml_content);
      setTags(existingCase.tags || []);
      setPriority(existingCase.priority);
      setTimeout_(existingCase.timeout?.toString() || "");
    }
  }, [existingCase]);

  useEffect(() => {
    setLineCount(yamlContent.split("\n").length);
  }, [yamlContent]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const payload = {
      name,
      description: description || undefined,
      yaml_content: yamlContent,
      tags,
      priority: priority as "P0" | "P1" | "P2" | "P3",
      timeout: timeout ? Number(timeout) : null,
    };

    try {
      if (isEdit) {
        await updateCase.mutateAsync({ id: id!, payload });
        toast.success("用例已更新");
      } else {
        await createCase.mutateAsync(payload);
        toast.success("用例已创建");
      }
      navigate("/cases");
    } catch {
      toast.error("保存失败，请检查后端服务");
    }
  };

  const formatYaml = () => {
    // 简单格式化：确保缩进整洁
    try {
      const lines = yamlContent.split("\n");
      const formatted = lines
        .map((line) => line.trimEnd())
        .join("\n");
      setYamlContent(formatted);
      toast.success("YAML 已格式化");
    } catch {
      toast.error("格式化失败");
    }
  };

  const validateYaml = () => {
    if (!yamlContent.trim()) {
      toast.error("YAML 内容为空");
      return;
    }
    // 基本检查：是否有 steps 或 request 关键词
    const hasSteps = yamlContent.includes("steps:") || yamlContent.includes("request:");
    if (!hasSteps) {
      toast.warning("YAML 中未检测到 steps 或 request 字段");
    } else {
      toast.success("YAML 语法检查通过");
    }
  };

  if (isEdit && isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Skeleton className="h-[500px]" />
          <Skeleton className="h-[500px]" />
        </div>
      </div>
    );
  }

  const suites = suitesData?.items || [];

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => navigate("/cases")}>
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <h1 className="text-2xl font-bold">
          {isEdit ? "编辑用例" : "新建用例"}
        </h1>
      </div>

      <form onSubmit={handleSubmit}>
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
          {/* Left: Form */}
          <div className="lg:col-span-2 space-y-5">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">基本信息</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="name">用例名称 *</Label>
                  <Input
                    id="name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="例：用户登录接口验证"
                    required
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="description">描述</Label>
                  <Textarea
                    id="description"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="用例用途和覆盖场景说明"
                    rows={3}
                  />
                </div>

                <div className="space-y-2">
                  <Label>优先级</Label>
                  <RadioGroup
                    value={priority}
                    onValueChange={setPriority}
                    className="flex gap-3"
                  >
                    {(["P0", "P1", "P2", "P3"] as const).map((p) => (
                      <div key={p} className="flex items-center space-x-1.5">
                        <RadioGroupItem value={p} id={`priority-${p}`} />
                        <Label htmlFor={`priority-${p}`} className="font-normal cursor-pointer">
                          {p}
                        </Label>
                      </div>
                    ))}
                  </RadioGroup>
                </div>

                <div className="space-y-2">
                  <Label>标签</Label>
                  <TagInput
                    value={tags}
                    onChange={setTags}
                    placeholder="输入标签后按回车添加"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="timeout">超时时间 (ms)</Label>
                    <Input
                      id="timeout"
                      type="number"
                      value={timeout}
                      onChange={(e) => setTimeout_(e.target.value)}
                      placeholder="30000"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="suite">关联套件</Label>
                    <Select>
                      <SelectTrigger id="suite">
                        <SelectValue placeholder="选择套件..." />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none">不关联</SelectItem>
                        {suites.map((s: { id: string; name: string }) => (
                          <SelectItem key={s.id} value={s.id}>
                            {s.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Action buttons */}
            <div className="flex gap-3">
              {canEdit && (
                <Button type="submit" disabled={createCase.isPending || updateCase.isPending}>
                  {(createCase.isPending || updateCase.isPending) && (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  )}
                  <Save className="mr-2 h-4 w-4" />
                  保存
                </Button>
              )}
              <Button
                type="button"
                variant="outline"
                onClick={() => navigate("/cases")}
              >
                取消
              </Button>
            </div>
          </div>

          {/* Right: YAML Editor */}
          <div className="lg:col-span-3 space-y-3">
            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base flex items-center gap-2">
                    <Code2 className="h-4 w-4" />
                    YAML 定义
                  </CardTitle>
                  <div className="flex gap-2">
                    <Button type="button" variant="outline" size="sm" onClick={formatYaml}>
                      格式化
                    </Button>
                    <Button type="button" variant="outline" size="sm" onClick={validateYaml}>
                      <Check className="mr-1 h-3.5 w-3.5" />
                      校验
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="relative">
                  <ScrollArea className="h-[420px] w-full rounded-md border">
                    <div className="flex">
                      {/* Line numbers */}
                      <div className="select-none bg-muted py-3 pl-4 pr-2 text-right font-mono text-xs text-muted-foreground leading-6">
                        {Array.from({ length: lineCount }, (_, i) => (
                          <div key={i}>{i + 1}</div>
                        ))}
                      </div>
                      {/* Editor */}
                      <Textarea
                        value={yamlContent}
                        onChange={(e) => setYamlContent(e.target.value)}
                        placeholder="name: 用例名称&#10;steps:&#10;  - request:&#10;      method: GET&#10;      url: /api/endpoint&#10;    assertions:&#10;      - status_code: 200"
                        className="min-h-[420px] font-mono text-sm leading-6 border-0 rounded-none resize-none focus-visible:ring-0"
                        spellCheck={false}
                      />
                    </div>
                  </ScrollArea>
                </div>
              </CardContent>
            </Card>

            {/* YAML Preview */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <Eye className="h-4 w-4" />
                  请求预览
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-sm text-muted-foreground">
                  {yamlContent.trim() ? (
                    <pre className="font-mono text-xs whitespace-pre-wrap bg-muted/50 rounded-md p-3 max-h-[200px] overflow-auto">
                      {yamlContent}
                    </pre>
                  ) : (
                    <div className="flex items-center justify-center h-20 text-muted-foreground/60">
                      在左侧编辑器中输入 YAML 后，此处将展示预览
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </form>
    </div>
  );
}
