# 🚀 AutoTest Framework — 企业级 API 自动化测试框架

> Python 3.10+ / pytest / httpx / YAML 驱动

## 特性

- **YAML 驱动** — 测试人员写 YAML，零代码完成用例编写
- **变量系统** — 多级变量作用域，内置函数（uuid、timestamp、md5 等）
- **断言引擎** — 16 种操作符，支持 JSONPath、正则、嵌套校验
- **数据库集成** — setup/teardown 中执行 SQL，从查询结果提取变量
- **WebSocket 支持** — WS 接口收发消息、断言验证
- **多环境切换** — `--env=staging` 一行命令切换环境
- **Allure 报告** — 请求/响应/断言详情自动附加
- **并行执行** — pytest-xdist 多进程并发
- **CI/CD 就绪** — GitHub Actions / Jenkins / GitLab CI / Docker

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 编写用例

创建 `testcases/smoke/test_api.yaml`：

```yaml
name: 用户接口测试
base_url: "{{env.base_url}}"
tags: [smoke]

cases:
  - name: 获取用户列表
    request:
      method: GET
      path: /api/users
      params:
        page: 1
    expect:
      status_code: 200
      jsonpath:
        $.data.list: "not_null"
        $.data.total: ">0"
    extract:
      first_user_id: $.data.list[0].id

  - name: 获取单个用户
    request:
      method: GET
      path: /api/users/{{first_user_id}}
    expect:
      status_code: 200
      jsonpath:
        $.data.id: "{{first_user_id}}"
```

### 3. 运行测试

```bash
# 冒烟测试
make smoke

# 指定环境
pytest --env=staging -m smoke -v

# 并行执行
pytest -n 4

# 生成 Allure 报告
make report
```

## 目录结构

```
auto-test-framework/
├── config/                  # 配置目录
│   ├── config.yaml          # 全局配置
│   └── env.yaml             # 多环境配置
├── framework/               # 框架核心代码
│   ├── models.py            # 数据模型
│   ├── config.py            # 配置加载器
│   ├── parser.py            # YAML 解析器
│   ├── runner.py            # 测试执行引擎
│   ├── client.py            # HTTP 客户端
│   ├── assertion.py         # 断言引擎
│   ├── extractor.py         # 变量提取器
│   ├── fixtures_loader.py   # Fixture 加载器
│   ├── context.py           # 线程安全上下文
│   ├── db.py                # 数据库模块
│   ├── ws.py                # WebSocket 模块
│   ├── report.py            # Allure 报告适配
│   └── utils/               # 工具模块
├── testcases/               # YAML 测试用例
│   ├── smoke/               # 冒烟测试
│   └── regression/          # 回归测试
├── assertions/              # 自定义断言函数
├── conftest.py              # pytest 全局配置
├── Makefile                 # 常用命令
├── Dockerfile               # Docker 支持
└── requirements.txt         # 依赖
```

## 命令速查

| 命令 | 说明 |
|------|------|
| `make install` | 安装依赖 |
| `make smoke` | 运行冒烟测试 |
| `make regression` | 运行回归测试 |
| `make parallel` | 并行执行 |
| `make report` | 生成 Allure 报告 |
| `make collect` | 只列出用例不执行 |
| `make debug` | 调试模式 |
| `make clean` | 清理报告和日志 |

## 变量系统

### 变量作用域（优先级从低到高）

1. 内置变量
2. 全局配置变量
3. 环境变量（env.yaml）
4. 套件变量（YAML 文件顶层 variables）
5. 用例变量（case 级 variables）
6. extract 提取的变量

### 内置函数

| 函数 | 用法 | 说明 |
|------|------|------|
| `timestamp()` | `{{timestamp()}}` | Unix 时间戳（秒） |
| `timestamp_ms()` | `{{timestamp_ms()}}` | Unix 时间戳（毫秒） |
| `uuid4()` | `{{uuid4()}}` | 随机 UUID |
| `random_int(min, max)` | `{{random_int(1, 100)}}` | 随机整数 |
| `random_string(length)` | `{{random_string(10)}}` | 随机字符串 |
| `now(format)` | `{{now('%Y-%m-%d')}}` | 当前时间 |
| `base64_encode(str)` | `{{base64_encode('hello')}}` | Base64 编码 |
| `md5(str)` | `{{md5('test')}}` | MD5 哈希 |
| `sha256(str)` | `{{sha256('test')}}` | SHA256 哈希 |
| `env_var(key)` | `{{env_var('API_KEY')}}` | 读取环境变量 |

## 断言操作符

| 操作符 | 说明 | 示例 |
|--------|------|------|
| `eq` | 等于 | `value: 200` |
| `ne` | 不等于 | `operator: ne, value: 0` |
| `gt` / `gte` | 大于 / 大于等于 | `operator: gt, value: 0` |
| `lt` / `lte` | 小于 / 小于等于 | `operator: lt, value: 100` |
| `contains` | 包含 | `operator: contains, value: "success"` |
| `matches` | 正则匹配 | `operator: matches, value: "^[a-z]+$"` |
| `in` | 在列表中 | `operator: in, value: [1, 2, 3]` |
| `not_null` | 非空 | `operator: not_null` |
| `is_null` | 为空 | `operator: is_null` |
| `type` | 类型检查 | `operator: type, value: "list"` |
| `length` | 长度检查 | `operator: length, value: ">0"` |
| `between` | 范围检查 | `operator: between, value: [1, 100]` |

## CI/CD 集成

### GitHub Actions

自动在 push/PR/定时 时运行测试，结果发布到 GitHub Pages。

### Jenkins

```bash
# Jenkinsfile 已内置，直接在 Pipeline 中使用
```

### Docker

```bash
# 构建镜像
docker build -t autotest .

# 运行测试
docker run --rm -v $(pwd)/reports:/app/reports autotest --env=staging -m smoke
```

## License

MIT
