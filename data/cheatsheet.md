# Python 刷题 Cheatsheet

写给雨桐自己的语法速查。每次遇到"手一停就想不起来"的东西，随手记进对应 section。

---

## sorted / list.sort

```python
sorted(nums)                              # 升序，返回新 list
sorted(nums, reverse=True)                # 降序
sorted(words, key=len)                    # 按长度
sorted(pts, key=lambda p: (p[0], -p[1]))  # 多关键字：先 x 升，再 y 降
nums.sort()                               # 原地，返回 None（别拿返回值！）

# 稳定排序：相等元素保持原顺序，做多轮排序时可以链式利用
```

## defaultdict / Counter

```python
from collections import defaultdict, Counter

d = defaultdict(list)
d[key].append(v)                          # 不用先判 key 存不存在

d = defaultdict(int)                      # 计数
d[key] += 1

cnt = Counter("abcabc")                   # {'a':2, 'b':2, 'c':2}
cnt.most_common(2)                        # [('a',2),('b',2)]  按频次降序
Counter(a) == Counter(b)                  # 判两个字符串是否 anagram
```

## heapq（最小堆）

```python
import heapq

h = []
heapq.heappush(h, x)
smallest = heapq.heappop(h)               # O(log n)
h[0]                                      # peek，不弹出
heapq.heapify(nums)                       # 原地建堆 O(n)

# 最大堆：push 相反数
heapq.heappush(h, -x)
-heapq.heappop(h)

# 堆里放 tuple：先按第一个字段比较
heapq.heappush(h, (freq, word))

# 前 K 大 / 前 K 小
heapq.nlargest(k, nums)                   # 前 K 大
heapq.nsmallest(k, nums, key=...)         # 前 K 小
```

## bisect（二分）

```python
import bisect

# 保持有序数组，找插入位置
bisect.bisect_left(a, x)                  # x 应插入的最左位置（找第一个 >= x）
bisect.bisect_right(a, x)                 # x 应插入的最右位置（找第一个 > x）
bisect.insort(a, x)                       # 插入并保持有序

# 手写二分模板（推荐记这个）
lo, hi = 0, len(nums)
while lo < hi:
    mid = (lo + hi) // 2
    if nums[mid] < target:
        lo = mid + 1
    else:
        hi = mid
# lo 就是第一个 >= target 的位置
```

## deque（双端队列 / 队列）

```python
from collections import deque

q = deque()
q.append(x)          # 右入
q.appendleft(x)      # 左入
q.pop()              # 右出
q.popleft()          # 左出   ← BFS 的队列出队

# 滑动窗口最大值：单调递减 deque 存下标
```

## itertools

```python
from itertools import combinations, permutations, product, accumulate

list(combinations([1,2,3], 2))            # [(1,2),(1,3),(2,3)]  组合
list(permutations([1,2,3], 2))            # 排列（有序）
list(product([0,1], repeat=3))            # 笛卡尔积，8 种 3 位二进制
list(accumulate([1,2,3,4]))               # [1,3,6,10]  前缀和一行
list(accumulate(nums, max))               # 前缀最大
```

## functools.cache（记忆化）

```python
from functools import cache, lru_cache

@cache                                    # Python 3.9+，无 maxsize
def dp(i, j):
    ...

@lru_cache(maxsize=None)                  # 老版本兼容
def dp(i, j):
    ...
```

## 字符串常用

```python
s.split()                                 # 按空白切
s.split(",")
",".join(lst)                             # lst 里必须都是 str

s.isdigit(), s.isalpha(), s.isalnum()
s.lower(), s.upper()
s.strip(), s.lstrip(), s.rstrip()

s.find(sub)                               # 找不到返回 -1（不像 index() 抛错）
s.count(sub)

# 反转
s[::-1]

# 字符 ↔ 数字
ord('a')                                  # 97
chr(97)                                   # 'a'
ord(c) - ord('a')                         # 字母映到 0-25
```

## 列表 / 切片高频

```python
nums[::-1]                                # 反转
nums[i:j]                                 # 半开区间 [i, j)
nums[::2]                                 # 每 2 个取 1 个

# 二维初始化：坑！
grid = [[0] * n for _ in range(m)]        # ✓ 正确
grid = [[0] * n] * m                      # ✗ 错！每行是同一个对象

# 展平
flat = [x for row in matrix for x in row]

# 枚举
for i, x in enumerate(nums):
    ...
for i, x in enumerate(nums, start=1):
    ...

# 打包 / 解包
for a, b in zip(a_list, b_list):
    ...
```

## 位运算速查

```python
x & 1                                     # 判奇偶
x >> 1                                    # 除以 2
x & (x - 1)                               # 消掉最低位的 1（Brian Kernighan）
bin(x).count('1')                         # 1 的个数
x ^ y                                     # 异或：相同为 0，不同为 1
                                          # 性质：a^a=0, a^0=a → 找出唯一元素
```

## 图 / 树 常见模板

```python
# 无向图邻接表
graph = defaultdict(list)
for u, v in edges:
    graph[u].append(v)
    graph[v].append(u)

# BFS 模板
from collections import deque
q = deque([start])
visited = {start}
while q:
    node = q.popleft()
    for nb in graph[node]:
        if nb not in visited:
            visited.add(nb)
            q.append(nb)

# DFS（递归）
def dfs(node):
    if node in visited:
        return
    visited.add(node)
    for nb in graph[node]:
        dfs(nb)

# 二叉树递归模板
def dfs(root):
    if not root:
        return ...
    left = dfs(root.left)
    right = dfs(root.right)
    return ...  # 分治合并
```

## 回溯模板

```python
def backtrack(path, choices):
    if 满足终止条件:
        res.append(path[:])   # 深拷贝！
        return
    for c in choices:
        if 剪枝条件:
            continue
        path.append(c)
        backtrack(path, 新 choices)
        path.pop()            # 撤销选择
```

## DP 常见套路

```python
# 一维滚动：只依赖 dp[i-1] 时压成一个变量
prev, curr = 0, 0
for x in nums:
    prev, curr = curr, max(curr, prev + x)

# 二维 DP 空间压缩：只依赖上一行 → 一维
dp = [0] * n
for i in range(m):
    for j in range(n):
        dp[j] = ...  # 注意遍历方向

# 常见维度：
# dp[i]        = 以 i 结尾 / 前 i 个的最优解
# dp[i][j]     = s1[:i] 和 s2[:j] 的关系（编辑距离、LCS）
# dp[i][j]     = 区间 [i,j] 的最优解（区间 DP）
```

## 常量 / 边界

```python
import math
math.inf, -math.inf                       # 或者 float('inf')
INT_MAX = 2**31 - 1

# 除法
a // b                                    # 整除，向下取整（Python 会 floor 到负无穷！）
int(a / b)                                # 向 0 截断
divmod(a, b)                              # (商, 余)
```

## 常见坑

- `list.sort()` 返回 `None`，别赋值。用 `sorted()` 才有返回值。
- 二维 list 用 `[[0]*n]*m` 会共享行引用；用 list comprehension。
- `dict` 遍历时改 key 会 RuntimeError；先拷贝 `list(d.keys())`。
- 递归深度默认 1000，深树要 `sys.setrecursionlimit(10**6)`。
- Python 整除对负数是 floor 不是截断：`-7 // 2 == -4`。
- `str` 不可变，拼接大量字符串用 `"".join(list)` 比 `+=` 快得多。
