import { useState } from "react";
import {
  useRecorderStatus,
  useRecorderSessions,
  useStartRecording,
  useStopRecording,
  usePauseRecording,
  useResumeRecording,
  useReplayHar,
  useGenerateCases,
} from "@/hooks/useRecorder";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table, TableBody, TableCell, TableHead,
  TableHeader, TableRow,
} from "@/components/ui/table";
import {
  Dialog, DialogContent, DialogDescription,
  DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";
import {
  Circle, Square, Pause, Play,
  Loader2, Radio, History, Diff, FileCode,
  CheckCircle2, XCircle, AlertTriangle, Info,
  Clock, Activity,
} from "lucide-react";
import type { PlaybackReport, DiffReport, DiffItem, RecordingSession } from "@/types";

export function RecorderPage() {
  const [sessionName, setSessionName] = useState("");
  const [selectedSession, setSelectedSession] = useState<RecordingSession | null>(null);
  const [replayDialogOpen, setReplayDialogOpen] = useState(false);
  const [replayResult, setReplayResult] = useState<PlaybackReport | null>(null);
  const [replaySessionId, setReplaySessionId] = useState<string>("");
  const [baseUrl, setBaseUrl] = useState("");
  const [genSuiteName, setGenSuiteName] = useState("");

  // React Query hooks
  const { data: status, isLoading: statusLoading } = useRecorderStatus();
  const { data: sessions, isLoading: sessionsLoading } = useRecorderSessions();
  const startRecording = useStartRecording();
  const stopRecording = useStopRecording();
  const pauseRecording = usePauseRecording();
  const resumeRecording = useResumeRecording();
  const replayHar = useReplayHar();
  const generateCases = useGenerateCases();

  const isRecording = status?.is_recording ?? false;
  const isPaused = status?.current_session?.state === "paused";
  const currentSession = status?.current_session;
  const sessionList = Array.isArray(sessions) ? sessions : [];

  const handleStart = async () => {
    try {
      await startRecording.mutateAsync({ session_name: sessionName || undefined });
      toast.success("录制已启动");
    } catch {
      toast.error("启动录制失败");
    }
  };

  const handleStop = async () => {
    try {
      await stopRecording.mutateAsync();
      toast.success("录制已停止并保存");
    } catch {
      toast.error("停止录制失败");
    }
  };

  const handlePause = async () => {
    try {
      await pauseRecording.mutateAsync();
      toast.success("录制已暂停");
    } catch {
      toast.error("暂停失败");
    }
  };

  const handleResume = async () => {
    try {
      await resumeRecording.mutateAsync();
      toast.success("录制已恢复");
    } catch {
      toast.error("恢复失败");
    }
  };

  const handleReplay = async (session: RecordingSession) => {
    setReplaySessionId(session.session_id);
    setSelectedSession(session);
    setReplayDialogOpen(true);
    setReplayResult(null);
    setBaseUrl("");
  };

  const handleReplaySubmit = async () => {
    if (!selectedSession) return;
    try {
      const result = await replayHar.mutateAsync({
        har_file: selectedSession.har_file,
        base_url: baseUrl || undefined,
      });
      setReplayResult(result);
    } catch {
      toast.error("回放失败");
    }
  };

  const handleGenerate = async (session: RecordingSession) => {
    if (!session.har_file) {
      toast.error("该会话没有对应的 HAR 文件");
      return;
    }
    try {
      const result = await generateCases.mutateAsync({
        har_file: session.har_file,
        suite_name: genSuiteName || session.name || undefined,
      });
      toast.success(`生成 ${result.case_count} 个用例: ${result.output_file}`);
    } catch {
      toast.error("用例生成失败");
    }
  };

  const formatDuration = (seconds: number): string => {
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    const m = Math.floor(seconds / 60);
    const s = Math.round(seconds % 60);
    return `${m}m ${s}s`;
  };

  const diffSeverityIcon = (severity: string) => {
    switch (severity) {
      case "error": return <XCircle className="h-4 w-4 text-destructive" />;
      case "warning": return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
      default: return <Info className="h-4 w-4 text-blue-400" />;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">流量录制与回放</h1>
          <p className="text-sm text-muted-foreground mt-1">
            录制 HTTP 流量为 HAR 文件，回放对比生成差异报告，或自动生成回归测试用例
          </p>
        </div>
      </div>

      {/* Recording Control */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <Radio className="h-4 w-4" />
            录制控制
            {isRecording && (
              <Badge variant="destructive" className="ml-2 animate-pulse">
                ● REC
              </Badge>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-end gap-3">
            <div className="flex-1">
              <Label htmlFor="session-name" className="text-xs">会话名称（可选）</Label>
              <Input
                id="session-name"
                value={sessionName}
                onChange={(e) => setSessionName(e.target.value)}
                placeholder="回归测试录制"
                className="mt-1"
                disabled={isRecording}
              />
            </div>
            <div className="flex gap-2">
              {!isRecording ? (
                <Button
                  onClick={handleStart}
                  disabled={startRecording.isPending}
                  className="gap-2"
                >
                  {startRecording.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Circle className="h-4 w-4 fill-current text-red-500" />
                  )}
                  开始录制
                </Button>
              ) : (
                <>
                  {isPaused ? (
                    <Button
                      onClick={handleResume}
                      disabled={resumeRecording.isPending}
                      className="gap-2"
                      variant="outline"
                    >
                      <Play className="h-4 w-4" />
                      继续
                    </Button>
                  ) : (
                    <Button
                      onClick={handlePause}
                      disabled={pauseRecording.isPending}
                      variant="outline"
                      className="gap-2"
                    >
                      <Pause className="h-4 w-4" />
                      暂停
                    </Button>
                  )}
                  <Button
                    onClick={handleStop}
                    disabled={stopRecording.isPending}
                    variant="destructive"
                    className="gap-2"
                  >
                    <Square className="h-4 w-4" />
                    停止
                  </Button>
                </>
              )}
            </div>
          </div>

          {/* Status indicator */}
          {statusLoading ? (
            <Skeleton className="h-8 mt-3 w-64" />
          ) : currentSession ? (
            <div className="mt-3 flex items-center gap-4 text-sm text-muted-foreground">
              <span className="flex items-center gap-1">
                <Activity className="h-3.5 w-3.5" />
                状态:{" "}
                <Badge variant="outline" className="text-xs">
                  {isRecording ? "录制中" : isPaused ? "已暂停" : "空闲"}
                </Badge>
              </span>
              <span className="flex items-center gap-1">
                <Clock className="h-3.5 w-3.5" />
                时长: {formatDuration(currentSession.duration_seconds)}
              </span>
              <span>
                已记录: <strong>{status?.total_entries ?? currentSession.entry_count}</strong> 条请求
              </span>
            </div>
          ) : (
            <p className="mt-3 text-sm text-muted-foreground">
              暂无活跃录制会话
            </p>
          )}
        </CardContent>
      </Card>

      {/* Session History */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <History className="h-4 w-4" />
            录制会话历史
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {sessionsLoading ? (
            <div className="p-4 space-y-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : sessionList.length === 0 ? (
            <div className="py-12 text-center text-muted-foreground">
              <Radio className="h-10 w-10 mx-auto mb-2 opacity-30" />
              <p>暂无录制会话</p>
              <p className="text-xs mt-1">开始录制后，会话将出现在此处</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>会话名称</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead className="w-[100px]">条目数</TableHead>
                  <TableHead className="w-[80px]">耗时</TableHead>
                  <TableHead className="w-[180px]">时间</TableHead>
                  <TableHead className="w-[200px]">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sessionList.map((session) => (
                  <TableRow key={session.session_id}>
                    <TableCell className="font-medium">
                      {session.name || session.session_id}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className="text-xs">
                        {session.state === "recording" ? "录制中"
                          : session.state === "paused" ? "已暂停"
                          : "已完成"}
                      </Badge>
                    </TableCell>
                    <TableCell>{session.entry_count}</TableCell>
                    <TableCell>{formatDuration(session.duration_seconds)}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {session.started_at
                        ? new Date(session.started_at).toLocaleString()
                        : "-"}
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        {session.har_file && (
                          <>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleReplay(session)}
                              className="gap-1 h-7 text-xs"
                            >
                              <Diff className="h-3 w-3" />
                              回放
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleGenerate(session)}
                              disabled={generateCases.isPending}
                              className="gap-1 h-7 text-xs"
                            >
                              <FileCode className="h-3 w-3" />
                              生成
                            </Button>
                          </>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Replay Dialog */}
      <Dialog open={replayDialogOpen} onOpenChange={setReplayDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>回放与差异对比</DialogTitle>
            <DialogDescription>
              回放 {selectedSession?.name || replaySessionId} 录制的请求，比较实际响应与录制响应的差异。
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            {!replayResult && (
              <div className="space-y-3">
                <div className="space-y-2">
                  <Label htmlFor="base-url">回放基础 URL（可选）</Label>
                  <Input
                    id="base-url"
                    value={baseUrl}
                    onChange={(e) => setBaseUrl(e.target.value)}
                    placeholder="替换录制时的 host，如 http://localhost:8080"
                  />
                  <p className="text-xs text-muted-foreground">
                    留空则使用录制时的原始 URL。用于在不同环境回放同一条 HAR 文件。
                  </p>
                </div>
                <Button
                  onClick={handleReplaySubmit}
                  disabled={replayHar.isPending}
                  className="w-full gap-2"
                >
                  {replayHar.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Diff className="h-4 w-4" />
                  )}
                  开始回放
                </Button>
              </div>
            )}

            {replayResult && (
              <ReplayResultView report={replayResult} />
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setReplayDialogOpen(false)}>
              关闭
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Generate dialog */}
      <Dialog>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>生成测试用例</DialogTitle>
            <DialogDescription>
              输入套件名称，从 HAR 生成 YAML 测试用例
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div className="space-y-2">
              <Label htmlFor="suite-name">套件名称</Label>
              <Input
                id="suite-name"
                value={genSuiteName}
                onChange={(e) => setGenSuiteName(e.target.value)}
                placeholder="回归测试-用户模块"
              />
            </div>
          </div>
          <DialogFooter>
            <Button onClick={() => {}}>确定</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// Internal component: displays replay results
function ReplayResultView({ report }: { report: PlaybackReport }) {
  return (
    <div className="space-y-4">
      {/* Summary */}
      <Card>
        <CardContent className="py-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium text-lg">
                {report.pass_rate > 80 ? (
                  <span className="text-green-600">通过率 {report.pass_rate}%</span>
                ) : report.pass_rate > 50 ? (
                  <span className="text-yellow-600">通过率 {report.pass_rate}%</span>
                ) : (
                  <span className="text-red-600">通过率 {report.pass_rate}%</span>
                )}
              </p>
              <p className="text-sm text-muted-foreground mt-1">
                共 {report.total_entries} 条:{" "}
                {report.matched_count} 匹配,{" "}
                {report.failed_count} 失败,{" "}
                {report.error_count} 错误
                {" · "}耗时 {report.duration_seconds}s
              </p>
            </div>
            <div className="flex gap-3 text-center">
              <div>
                <div className="text-lg font-bold text-green-600">{report.matched_count}</div>
                <div className="text-xs text-muted-foreground">匹配</div>
              </div>
              <div>
                <div className="text-lg font-bold text-red-600">{report.failed_count}</div>
                <div className="text-xs text-muted-foreground">不匹配</div>
              </div>
              <div>
                <div className="text-lg font-bold text-yellow-600">{report.error_count}</div>
                <div className="text-xs text-muted-foreground">错误</div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Results table */}
      <div className="space-y-3">
        {report.results.map((result) => (
          <Card key={result.entry_index}>
            <CardContent className="py-3">
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className="font-mono text-xs">
                      {result.method}
                    </Badge>
                    {result.matched ? (
                      <CheckCircle2 className="h-4 w-4 text-green-500" />
                    ) : (
                      <XCircle className="h-4 w-4 text-red-500" />
                    )}
                    <span className="text-sm font-medium truncate">{result.url}</span>
                  </div>
                  <div className="flex gap-4 mt-1 text-xs text-muted-foreground">
                    <span>
                      录制: <strong>{result.recorded_status}</strong> → 回放:{" "}
                      <strong>{result.actual_status}</strong>
                    </span>
                    <span>
                      录制耗时: {result.recorded_elapsed_ms}ms · 回放耗时:{" "}
                      {result.actual_elapsed_ms}ms
                    </span>
                  </div>
                  {result.error && (
                    <p className="text-xs text-destructive mt-1">{result.error}</p>
                  )}

                  {/* Diff details */}
                  {result.diff_report && result.diff_report.diffs.length > 0 && (
                    <div className="mt-2 border-t pt-2">
                      <p className="text-xs font-medium mb-1">
                        {result.diff_report.summary}
                      </p>
                      <div className="space-y-1">
                        {result.diff_report.diffs.map((diff, i) => (
                          <DiffDetail key={i} diff={diff} />
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

// Diff detail component
function DiffDetail({ diff }: { diff: DiffItem }) {
  return (
    <div className="flex items-start gap-2 text-xs bg-muted/50 rounded px-2 py-1">
      {diffSeverityIcon(diff.severity)}
      <div className="flex-1">
        <span className="font-mono font-medium">{diff.path}</span>
        <span className="text-muted-foreground">: {diff.message}</span>
        <div className="flex gap-3 mt-0.5">
          <span className="text-green-600">
            录制: {JSON.stringify(diff.recorded)}
          </span>
          <span className="text-red-600">
            实际: {JSON.stringify(diff.actual)}
          </span>
        </div>
      </div>
    </div>
  );
}

// Helper (duplicates the one from inside the component)
function diffSeverityIcon(severity: string) {
  switch (severity) {
    case "error": return <XCircle className="h-4 w-4 text-destructive" />;
    case "warning": return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
    default: return <Info className="h-4 w-4 text-blue-400" />;
  }
}
