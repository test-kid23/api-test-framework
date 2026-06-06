---
name: remove-integration-tests-from-ci
overview: 从 GitHub CI 中移除依赖外部网络（httpbin.org）的集成测试步骤，只保留可离线运行的单元测试。
todos:
  - id: remove-integration-step
    content: 删除 .github/workflows/test.yml 中第69-82行 "Run integration tests" step，使单元测试直接衔接 Allure Report 生成
    status: completed
---

## 需求

移除 GitHub CI workflow 中依赖外部网络的集成测试步骤。

## 背景

- `testcases/` 目录下 5 个 YAML 用例全部访问 `httpbin.org`，CI 环境 DNS 解析失败
- `tests/` 目录下 12 个单元测试模块完全覆盖框架核心逻辑，无需任何外部网络
- 集成测试步骤已设置 `continue-on-error: true`，失败不阻塞 CI，但每次红色报错影响 CI 可见性

## 改动范围

仅修改 `.github/workflows/test.yml`，删除 "Run integration tests" step（第69-82行），保留其余所有步骤不变。

## 实现方式

直接删除 `test.yml` 第69-82行的 YAML block：

```
      - name: Run integration tests
        env:
          ENV: ${{ github.event.inputs.environment || 'staging' }}
          DB_PASSWORD: ${{ secrets.DB_PASSWORD }}
          API_KEY: ${{ secrets.API_KEY }}
        run: |
          pytest testcases/ --env=${{ env.ENV }} \
                 -m "${{ github.event.inputs.tags || 'smoke' }}" \
                 -n auto \
                 --alluredir=reports/allure-results \
                 --no-persist \
                 --tb=short \
                 -v
        continue-on-error: true
```

删除后，单元测试步骤直接衔接 Allure Report 生成步骤。

## 影响分析

- **CI 时间缩短**：不再执行网络超时的集成测试
- **覆盖率不变**：`tests/` 下 12 个模块已覆盖 runner、配置、断言、提取器、持久化、脱敏等全部核心逻辑
- **不破坏现有功能**：集成测试步骤原本就 `continue-on-error: true`，删除不影响 CI 通过/失败状态
- **本地仍可手动运行**：`pytest testcases/ --env=dev` 在本地网络可达时仍可用