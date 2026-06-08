import { useState, useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useCase, useCreateCase, useUpdateCase } from "@/hooks/useCases";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { ArrowLeft, Loader2, Save } from "lucide-react";

export function CaseEditPage() {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const isEdit = !!id;

  const { data: existingCase, isLoading } = useCase(id);
  const createCase = useCreateCase();
  const updateCase = useUpdateCase();

  const [name, setName] = useState("");
  const [yamlContent, setYamlContent] = useState("");
  const [tagsInput, setTagsInput] = useState("");
  const [priority, setPriority] = useState<string>("P2");

  useEffect(() => {
    if (existingCase) {
      setName(existingCase.name);
      setYamlContent(existingCase.yaml_content);
      setTagsInput(existingCase.tags?.join(", ") || "");
      setPriority(existingCase.priority);
    }
  }, [existingCase]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const tags = tagsInput
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean);

    const payload = {
      name,
      yaml_content: yamlContent,
      tags,
      priority: priority as "P0" | "P1" | "P2" | "P3",
    };

    try {
      if (isEdit) {
        await updateCase.mutateAsync({ id: id!, payload });
      } else {
        await createCase.mutateAsync(payload);
      }
      navigate("/cases");
    } catch {
      // error handled by tanstack query
    }
  };

  if (isEdit && isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-[500px] w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => navigate("/cases")}>
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <h1 className="text-2xl font-bold">
          {isEdit ? "编辑用例" : "新建用例"}
        </h1>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">用例信息</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="name">用例名称 *</Label>
              <Input
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="输入用例名称"
                required
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="priority">优先级</Label>
                <Select value={priority} onValueChange={setPriority}>
                  <SelectTrigger id="priority">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="P0">P0 - 最高</SelectItem>
                    <SelectItem value="P1">P1 - 高</SelectItem>
                    <SelectItem value="P2">P2 - 中</SelectItem>
                    <SelectItem value="P3">P3 - 低</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="tags">标签（逗号分隔）</Label>
                <Input
                  id="tags"
                  value={tagsInput}
                  onChange={(e) => setTagsInput(e.target.value)}
                  placeholder="smoke, crud, P0"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="yaml">YAML 内容 *</Label>
              <Textarea
                id="yaml"
                value={yamlContent}
                onChange={(e) => setYamlContent(e.target.value)}
                placeholder="在此输入 YAML 格式的测试用例内容..."
                className="min-h-[400px] font-mono text-sm"
                required
              />
            </div>

            <div className="flex gap-3 pt-2">
              <Button type="submit" disabled={createCase.isPending || updateCase.isPending}>
                {(createCase.isPending || updateCase.isPending) && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                <Save className="mr-2 h-4 w-4" />
                保存
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => navigate("/cases")}
              >
                取消
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
