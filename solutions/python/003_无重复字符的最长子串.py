class Solution:
    def lengthOfLongestSubstring(self, s: str) -> int:
        hashSet = set()
        left, right = 0, 0
        ans = 0
        for right in range(0, len(s)):
            while (s[right] in hashSet):
                hashSet.remove(s[left])
                left += 1
            ans = max(ans, right - left + 1)
            hashSet.add(s[right])
        return ans