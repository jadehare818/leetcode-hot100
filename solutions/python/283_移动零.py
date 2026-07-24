class Solution:
    def moveZeroes(self, nums: List[int]) -> None:
        """
        Do not return anything, modify nums in-place instead.
        """
        left = 0
        for right in range(0, len(nums)):
            if nums[right] != 0:
                tmp = nums[right]
                nums[right] = nums[left]
                nums[left] = tmp
                left += 1
        