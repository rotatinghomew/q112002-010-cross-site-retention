# 跨考点复测关联资料

观察窗自结课日起算，第 7–10 日是第一轮，第 14–18 日是第二轮，首尾均计。同一技能的分值是统一的 0–4 等级；第二轮不少于第一轮且首轮至少为 2，记为保持。`eligible` 是这一技能的结课观察资格。改进线是成熟有资格学员中至少 70% 保持；配对缺失和无可用作答需另列覆盖，不当作零。区间应对仍有可能的批内关联取界；在图内可以保留未能配对的结果，没有数据可推断结果时不得把分值填成零。
`token` 是考点某一次作答的随机号，按考点、轮次和 token 识别；一张卷可评多个技能。同一个人的同轮同技能若有两份同等有效的作答，先保留争议，不能用分高者代替。候选关系只说明可能，`excluded` 为排除，`confirmed` 是考务确认，`withdrawn` 撤回上一次确认、恢复候选。每一行更新其 `edge` 在当时的状态，日按资料获知时间记。
真实联系信息不在资料中；`contact` 是当地考务交接用的合成号码，`routes` 指明这个号码已经可用于联系哪个名册人。`invitations` 是早期操作的回执，`confirmed` 由学员决定。可核实证据包由考务列出会提供哪些候选关系的裁定及所需分钟，不保证其裁定结果；限时清单不是学生联系人清单。

## 资料格式

资料是匿名合成登记，不包含真实学生、真实成绩或外部访问地址。UTF-8 JSON，每张表是对象数组；`null` 表示该字段无已知值。`records/catalog.json` 记录每张表的字段。

- `cohorts`：结课名册，含可分析技能。 字段：`student`、`cohort`、`ended`、`eligible`。
- `results`：单个考点编号可能有多科得分，不能据成绩确定身份。 字段：`site`、`wave`、`token`、`skill`、`day`、`score`、`independent`。
- `links`：候选、排除、确认和撤回的陆续登记。 字段：`edge`、`student`、`site`、`wave`、`token`、`state`、`day`。
- `routes`：当地考务核实的联系索引，结束日不含。 字段：`student`、`contact`、`from_day`、`until_day`。
- `review_packages`：一次可调阅的一组考务凭证。 字段：`package`、`edges`、`minutes`、`ready`。
- `review_windows`：每次可安排的核实时间。 字段：`day`、`minutes`。
- `invitations`：考务先前发出的复测安排与回执。 字段：`invitation`、`student`、`skill`、`basis`、`contact`、`issued`、`status`。
- `locks`：过往课堂会引用的资料截止点。 字段：`issue`、`day`、`cohort`。

## 本地查看

使用 Python 3.11 标准库，无需安装包。用 `python3 record_reader.py` 检查并列出收到的表行数；也可传入同格式资料目录。用 `python3 -m unittest discover -s tests -v` 检查资料契约。读取入口不会计算分析结果。
