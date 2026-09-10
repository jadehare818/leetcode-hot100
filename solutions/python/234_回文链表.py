"""
234. 回文链表 (简单) · 链表
https://leetcode.cn/problems/palindrome-linked-list/
"""
class ListNode:
    def __init__(self, val=0, next=None):
        self.val = val
        self.next = next

def isPalindrome(head):
    cur = head
    n = 0
    while cur:
        n += 1
        cur = cur.next
    pre = head
    print(n)
    for i in range((n - 1) // 2):
        pre = pre.next
    cur = pre.next

    while cur:
        tmp = cur.next
        cur.next = pre
        pre = cur
        cur = tmp
    cur = head
    cur2 = head
    while cur:
        print(cur.val)
        cur = cur.next
    cur = head
    for i in range((n + 1) // 2):
        cur2 = cur2.next
    while cur2:
        if cur.val == cur2.val:
            cur = cur.next
            cur2 = cur2.next
        else:
            return False
    return True

n1 = ListNode(1)
n2 = ListNode(2)
n3 = ListNode(2)
n4 = ListNode(1)

n1.next = n2
n2.next = n3
n3.next = n4
print(isPalindrome(n1))