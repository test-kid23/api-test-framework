import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Plus, Pencil, Trash2, Play, Package, Loader2, Search, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter,
  DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel,
  AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  useSuites, useCreateSuite, useUpdateSuite, useDeleteSuite,
} from "@/hooks/useSuites";
import { useCases } from "@/hooks/useCases";
import { executionsApi } from "@/api/executions";
import { toast } from "sonner";
import type { Suite, SuiteCreate } from "@/types";
import { usePermission } from "@/hooks/usePermission";

export function SuitesPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const { canEdit } = usePermission();
  const { data, isLoading } = useSuites({ page: 1, page_size: 100, search: search || undefined });
  const { data: casesData } = useCases({ page: 1, page_size: 200 });
  const createSuite = useCreateSuite();
  const updateSuite = useUpdateSuite();
  const deleteSuite = useDeleteSuite();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingSuite, setEditingSuite] = useState<Suite | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Suite | null>(null);
  const [triggeringId, setTriggeringId] = useState<string | null>(null);

  // Form state
  const [formName, setFormName] = useState("");
  const [formDesc, setFormDesc] = useState("");
  const [formCaseIds, setFormCaseIds] = useState<string[]>([]);

  const suites = data?.items ?? [];
  const allCases = casesData?.items ?? [];

  function openCreate() {
    setEditingSuite(null);
    setFormName("");
    setFormDesc("");
    setFormCaseIds([]);
    setDialogOpen(true);
  }

  function openEdit(suite: Suite) {
    setEditingSuite(suite);
    setFormName(suite.name);
    setFormDesc(suite.description || "");
    setFormCaseIds(suite.case_ids || []);
    setDialogOpen(true);
  }

  async function handleSave() {
    if (!formName.trim()) {
      toast.error(t("suites.enterNameToast"));
      return;
    }
    const payload: SuiteCreate = {
      name: formName.trim(),
      description: formDesc.trim() || undefined,
      case_ids: formCaseIds,
    };
    try {
      if (editingSuite) {
        await updateSuite.mutateAsync({ id: editingSuite.id, payload });
        toast.success(t("suites.updated"));
      } else {
        await createSuite.mutateAsync(payload);
        toast.success(t("suites.created"));
      }
      setDialogOpen(false);
    } catch {
      toast.error(t("suites.saveFailed"));
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    try {
      await deleteSuite.mutateAsync(deleteTarget.id);
      toast.success(t("suites.deleted"));
    } catch {
      toast.error(t("suites.deleteFailed"));
    }
  }

  async function handleTrigger(suiteId: string) {
    setTriggeringId(suiteId);
    try {
      const result = await executionsApi.trigger({
        case_ids: [],
        suite_id: suiteId,
      });
      toast.success(t("suites.triggered", { name: result.name }));
      navigate(`/executions/${result.id}`);
    } catch {
      toast.error(t("suites.triggerFailed"));
    } finally {
      setTriggeringId(null);
    }
  }

  function toggleCaseId(caseId: string) {
    setFormCaseIds((prev) =>
      prev.includes(caseId) ? prev.filter((id) => id !== caseId) : [...prev, caseId]
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">{t("suites.title")}</h1>
        {canEdit && (
        <Button onClick={openCreate}>
          <Plus className="mr-2 h-4 w-4" />{t("suites.create")}
        </Button>
        )}
      </div>

      {/* Search */}
      <div className="flex items-center gap-2">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder={t("suites.searchPlaceholder")}
            className="pl-8"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        {search && (
          <Button variant="ghost" size="sm" onClick={() => setSearch("")}>
            <X className="h-4 w-4" />{t("suites.clearSearch")}
          </Button>
        )}
      </div>

      {/* Suite Cards Grid */}
      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Card key={i} className="overflow-hidden">
              <CardHeader className="pb-2">
                <Skeleton className="h-5 w-2/3" />
                <Skeleton className="h-4 w-full mt-1" />
              </CardHeader>
              <CardContent className="pb-3">
                <div className="flex gap-2">
                  <Skeleton className="h-5 w-20 rounded-full" />
                  <Skeleton className="h-5 w-14 rounded-full" />
                </div>
              </CardContent>
              <CardFooter className="flex items-center gap-2 pt-0">
                <Skeleton className="h-8 flex-1 rounded-md" />
                <Skeleton className="h-8 w-8 rounded-md" />
                <Skeleton className="h-8 w-8 rounded-md" />
              </CardFooter>
            </Card>
          ))}
        </div>
      ) : suites.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="py-0">
            <EmptyState
              icon={Package}
              title={search ? t("suites.noMatch") : t("suites.noSuites")}
              description={search ? t("suites.tryOtherKeyword") : t("suites.noSuitesDesc")}
              action={
                search
                  ? { label: t("suites.clearSearch"), onClick: () => setSearch("") }
                  : canEdit ? { label: t("suites.create"), onClick: openCreate } : undefined
              }
            />
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {suites.map((suite) => (
            <Card key={suite.id} className="group transition-shadow hover:shadow-md">
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between">
                  <div className="min-w-0 flex-1">
                    <CardTitle className="text-base truncate">{suite.name}</CardTitle>
                    {suite.description && (
                      <CardDescription className="mt-1 line-clamp-2">
                        {suite.description}
                      </CardDescription>
                    )}
                  </div>
                </div>
              </CardHeader>
              <CardContent className="pb-3">
                <div className="flex items-center gap-2">
                  <Badge variant="secondary" className="text-xs">
                    <Package className="mr-1 h-3 w-3" />
                    {(suite.case_ids?.length ?? 0)} {t("suites.casesUnit")}
                  </Badge>
                  {suite.tags?.map((tag) => (
                    <Badge key={tag} variant="outline" className="text-xs">
                      {tag}
                    </Badge>
                  ))}
                </div>
              </CardContent>
              <CardFooter className="flex items-center gap-2 pt-0">
                {canEdit ? (
                  <>
                    <Button
                      variant="default"
                      size="sm"
                      className="flex-1"
                      onClick={() => handleTrigger(suite.id)}
                      disabled={triggeringId === suite.id}
                    >
                      {triggeringId === suite.id ? (
                        <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Play className="mr-1 h-3.5 w-3.5" />
                      )}
                      {t("suites.triggerExecution")}
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => openEdit(suite)}>
                      <Pencil className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setDeleteTarget(suite)}
                    >
                      <Trash2 className="h-3.5 w-3.5 text-destructive" />
                    </Button>
                  </>
                ) : (
                  <span className="text-sm text-muted-foreground">
                    {(suite.case_ids?.length ?? 0)} {t("suites.casesUnit")}
                  </span>
                )}
              </CardFooter>
            </Card>
          ))}
        </div>
      )}

      {/* Create / Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-xl">
          <DialogHeader>
            <DialogTitle>{editingSuite ? t("suites.editTitle") : t("suites.createTitle")}</DialogTitle>
            <DialogDescription>
              {editingSuite ? t("suites.editDesc") : t("suites.createDesc")}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="suite-name">{t("suites.nameLabel")}</Label>
              <Input
                id="suite-name"
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                placeholder={t("suites.namePlaceholder")}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="suite-desc">{t("suites.descLabel")}</Label>
              <Textarea
                id="suite-desc"
                value={formDesc}
                onChange={(e) => setFormDesc(e.target.value)}
                placeholder={t("suites.descPlaceholder")}
                rows={3}
              />
            </div>
            <div className="space-y-2">
              <Label>{t("suites.linkedCases")}</Label>
              <div className="text-xs text-muted-foreground mb-2">
                {t("suites.selectedCount", { selected: formCaseIds.length, total: allCases.length })}
              </div>
              <ScrollArea className="h-48 rounded-md border">
                <div className="p-3 space-y-1">
                  {allCases.length === 0 ? (
                    <p className="text-sm text-muted-foreground p-2">{t("suites.noAvailableCases")}</p>
                  ) : (
                    allCases.map((c) => (
                      <label
                        key={c.id}
                        className="flex items-center gap-2 rounded-md px-2 py-1.5 hover:bg-accent cursor-pointer"
                      >
                        <Checkbox
                          checked={formCaseIds.includes(c.id)}
                          onCheckedChange={() => toggleCaseId(c.id)}
                        />
                        <span className="text-sm truncate flex-1">{c.name}</span>
                        <Badge variant="outline" className="text-xs flex-shrink-0">
                          {c.priority}
                        </Badge>
                      </label>
                    ))
                  )}
                </div>
              </ScrollArea>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button
              onClick={handleSave}
              disabled={createSuite.isPending || updateSuite.isPending}
            >
              {(createSuite.isPending || updateSuite.isPending) && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              {t("common.save")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirm */}
      <AlertDialog
        open={!!deleteTarget}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("suites.confirmDeleteTitle")}</AlertDialogTitle>
            <AlertDialogDescription>
              {t("suites.confirmDeleteDesc", { name: deleteTarget?.name ?? "" })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t("common.cancel")}</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteSuite.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              {t("suites.deleteBtn")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
