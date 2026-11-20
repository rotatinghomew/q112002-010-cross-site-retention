# 无辅助迁移复测考务资料

练习完成日为第零日。两个观察窗为第 7–10 日与第 14–18 日，首尾都计；更早和更晚的记录只供追溯，不替代可比观察。`certificates` 是考务已确认的卷、目标、观察窗与可比组；不需要重新估计量尺。同可比组的 `score` 是统一的 0–4 等级，2 以下是对应目标的复检条件。
`exposures` 的 `kind` 为空不使用；讲解是上课发生的事件，个人接卷也是曝光。`day` 是发生日，`received` 是登记到达日。先前在独立任务或复测收到试卷不影响该次观察，但之后不能再用同题族。无辅助标记以监考回执为准。
`agenda` 是校务给出的复测场次，`max_sittings` 是场次总人数，`stock` 是同一场次该卷的最大份数。`phase` 表示第一次和第二次排表而非观察窗。录入已确认预约，以及教学组过去锁定批次的资料截点，支持复核当时可知事实。

## 资料格式

资料是匿名合成登记，不包含真实学生、真实成绩或外部访问地址。UTF-8 JSON，每张表是对象数组；`null` 表示该字段无已知值。`records/catalog.json` 记录每张表的字段。

- `practice`：学生在对应目标完成练习的日期。 字段：`student`、`room`、`goal`、`ended`。
- `forms`：试卷编号及题族。 字段：`form`、`family`。
- `certificates`：window 为 short 或 long；scale 同名可比。 字段：`form`、`goal`、`window`、`scale`。
- `observations`：无辅助任务或之前的复测记录。 字段：`student`、`form`、`goal`、`day`、`score`、`independent`。
- `exposures`：按班讲题或学生个人领卷，另一范围填空。 字段：`room`、`student`、`family`、`day`、`received`、`kind`。
- `agenda`：监考安排，两次排期可联动试算。 字段：`session`、`day`、`phase`、`proctor`、`max_sittings`。
- `stock`：场次可用卷份数。 字段：`session`、`form`、`copies`。
- `availability`：学生确认可到安排。 字段：`student`、`session`。
- `appointments`：已确认与尚待确认的邀请。 字段：`student`、`session`、`form`、`state`、`agreed`。
- `locks`：历史批次引用的业务日截点。 字段：`key`、`cutoff`、`room`。

## 本地查看

使用 Python 3.11 标准库，无需安装包。用 `python3 record_reader.py` 检查并列出收到的表行数；也可传入同格式资料目录。用 `python3 -m unittest discover -v` 检查资料契约。读取入口不会计算分析结果。
