---
name: fix-allure-report-gh-pages
overview: 修复 GitHub Actions 中 Allure 报告生成和 GitHub Pages 部署的两个问题：1) simple-elf/allure-report-action@v1 Docker 构建失败；2) allure-history 目录不存在导致 peaceiris/actions-gh-pages 部署失败。同时解决矩阵策略下多 job 并发部署的冲突。
todos:
  - id: remove-allure-from-matrix
    content: 从 test 矩阵 job 中移除 Generate Allure Report 和 Deploy to GitHub Pages 步骤，并去掉 allure-history 目录的预创建
    status: completed
  - id: add-deploy-report-job
    content: 新增独立 deploy-report job，下载所有矩阵 artifact、合并 allure results、用 npm allure-commandline 生成报告并部署到 gh-pages
    status: completed
    dependencies:
      - remove-allure-from-matrix
---

## 问题分析

GitHub Actions CI 中 `test (3.11)` / `test (3.12)` 矩阵 job 失败，有两个连锁错误：

1. **`simple-elf/allure-report-action@v1` Docker 构建失败（exit code 1）**：该 Action 的 Dockerfile 与新版 GitHub Actions runner 镜像不兼容，导致报告无法生成。
2. **`peaceiris/actions-gh-pages@v4` 部署失败**：因步骤 1 失败后 `allure-history` 目录为空，部署时 `scandir` 找不到该目录报 `ENOENT`。
3. **矩阵竞态条件**：当前设计下两个矩阵 job（3.11 和 3.12）分别执行报告生成和 gh-pages 部署，同时操作同一个 gh-pages 分支可能产生冲突。

## 修复目标

- 移除 broken 的 `simple-elf/allure-report-action@v1`，替换为原生 `allure-commandline` CLI（npm 包）
- 将报告生成与部署从矩阵 job 中抽离为独立的 `deploy-report` job，单次执行消除竞态
- 合并来自两个矩阵 job 的 Allure results artifact，生成统一的测试报告部署到 GitHub Pages

## 技术方案

### 核心策略：矩阵 job 只生产 artifact，独立 job 消费并部署

```
test (3.11) ──► upload artifact: allure-results-py3.11 ──┐
                                                          ├──► deploy-report ──► gh-pages
test (3.12) ──► upload artifact: allure-results-py3.12 ──┘
```

- **test job**：保留测试执行和 artifact 上传，移除报告生成和 gh-pages 部署步骤
- **deploy-report job**：`needs: test`，`if: always()`，下载所有 artifact → 合并 → 生成 Allure 报告 → 部署

### 报告生成工具替换

| 之前 | 之后 |
| --- | --- |
| `simple-elf/allure-report-action@v1`（Docker，不稳定） | `npm install -g allure-commandline` + `allure generate`（原生 CLI，稳定） |


`allure-commandline` 是 Java-based CLI 的 npm 封装，与 runner 镜像兼容性好，无需 Docker。

### 变更文件

仅修改 `.github/workflows/test.yml`：

1. **test job**：删除第 82-95 行（Generate Allure Report + Deploy report），第 47-51 行中移除 `mkdir -p allure-history`
2. **新增 deploy-report job**：在第 95 行后插入独立部署 job，包含下载 artifact、合并结果、安装 allure CLI、生成报告、部署四个步骤