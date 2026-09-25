class VerificationEngine:

    def verify(self, old_bugs, new_bugs, execution):

        if execution.get("error_type") == "Security Block":
            return {
                "verified": False,
                "fixed_count": 0,
                "remaining_count": len(new_bugs),
                "execution_success": False,
                "fixed_issues": [],
                "remaining_issues": [
                    b.get("type") for b in new_bugs
                ],
                "message": "Execution blocked for security reasons."
            }

        old_types = {b.get("type") for b in old_bugs}
        new_types = {b.get("type") for b in new_bugs}

        remaining = old_types & new_types
        fixed = old_types - new_types

        success = execution.get("success", False)

        verified = not remaining and success

        return {
            "verified": verified,
            "fixed_count": len(fixed),
            "remaining_count": len(remaining),
            "execution_success": success,
            "fixed_issues": list(fixed),
            "remaining_issues": list(remaining),
            "message": (
                "Code fixed and verified successfully."
                if verified
                else "Some original issues still remain."
            )
        }