# 术语规范与对照表

## 三条硬规则

1. **首次出现给原词**：`中文译名（English，缩写）`，之后统一用中文。例：`预训练模型（pre-trained model，PTM）`，后文一律写 `PTM` 或 `预训练模型`，不要中英混着换。
2. **缩写一经引入就固定**：PTM / CR / DE / HD / FSC / CDC / AD 直接当词用，不再展开。
3. **系统名、模型名、文件名、单位、数据类型不译**：Elf、Elves、QStore、zstd、SZ3、zfp、BTRBLOCKS、FastCDC、Hugging Face、float32、MB/s、GB。

## 数据缩减与压缩

| English | 中文 | 备注 |
|---|---|---|
| data reduction | 数据缩减 | 不要译"数据减少" |
| compression ratio (CR) | 压缩率 | 保持 CR 缩写 |
| deduplication | 去重 | 动词用"执行去重" |
| delta compression | 增量压缩 | 也可"差分压缩"，同一文档只用一种 |
| fixed-size chunking (FSC) | 定长分块 | |
| content-defined chunking (CDC) | 内容定义分块 | 不译"内容分块" |
| dictionary coding | 字典编码 | |
| length-distance pair | 长度-距离对 | |
| distance encoding (DE) | 距离编码 | |
| similarity / resemblance detection | 相似性检测 | |
| fingerprint | 指纹 | |
| super feature (SF) | 超级特征 | |
| storage footprint | 存储占用 | 不译"存储足迹" |
| error-bounded lossy compression | 误差有界有损压缩 | |
| near-lossless | 近无损 | |
| exponent field / mantissa / sign bit | 指数域 / 尾数 / 符号位 | |
| throughput | 吞吐量 | |
| pseudo-decimal encoding | 伪十进制编码 | |
| working set | 工作集 | |

## 模型与训练

| English | 中文 | 备注 |
|---|---|---|
| pre-trained model (PTM) | 预训练模型 | |
| model registry | 模型注册服务 | |
| model serving | 模型服务 | |
| model cascade / chaining | 模型级联 / 链式调用 | |
| distillation | 蒸馏 | |
| fine-tuning | 微调 | |
| inference | 推理 | |
| quantization | 量化 | |
| quantization-aware training | 量化感知训练 | |
| post-training quantization | 训练后量化 | |
| uniform quantization | 均匀量化 | |
| pruning (structured / unstructured) | 剪枝（结构化 / 非结构化） | |
| parameter | 参数 | |
| layer / chunk | 层 / 块 | "model chunk" = 模型块 |
| accuracy degradation (AD) | 精度退化 | |
| ablation study | 消融实验 | |
| baseline | 基线 | |
| fuzz testing | 模糊测试 | |
| cosine similarity | 余弦相似度 | |
| embedding | 嵌入 | |
| CDF (cumulative distribution) | 累积分布（CDF） | |

## 数据库方向常见词（译 AI×DB 论文时备用）

| English | 中文 |
|---|---|
| learned index | 学习型索引 |
| cardinality estimation | 基数估计 |
| query optimization | 查询优化 |
| predicate / selectivity | 谓词 / 选择率 |
| filtered ANN | 带过滤的近似最近邻 |
| top-k | 前 k 个（结果） |
| columnar storage | 列式存储 |
| data lake | 数据湖 |
| buffer pool | 缓冲池 |
| write-ahead log | 预写日志 |
| materialized view | 物化视图 |
| scan / join / aggregation | 扫描 / 连接 / 聚合 |

## 图注/表注写法

- `图 3：` `表 2：` 后紧跟说明，编号与原文一致；原图注首行是粗体的，只加粗"图 3："。
- 保留原文里图例的英文名（如 "Elves Compressed Size"），可用中文解释：`“Elves Compressed Size”（Elves 压缩后大小）`。
- 表注里解释缩写时保持缩写原样：`NLP：自然语言处理。CV：计算机视觉。`
