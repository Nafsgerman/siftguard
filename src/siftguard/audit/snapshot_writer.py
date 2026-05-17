def emit_blocked_mutation(
        self,
        case_id: str,
        attempted_action: str,
        reason: str,
        actor: str = "siftguard-agent",
    ) -> str:
        """
        Write a spoliation receipt for a blocked mutation attempt.
        Returns the receipt_id for confirmation logging.
        """
        import uuid
        receipt_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat() + "Z"
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO blocked_mutation
                    (receipt_id, case_id, attempted_action, reason, actor, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (receipt_id, case_id, attempted_action, reason, actor, timestamp),
            )
            conn.commit()
        return receipt_id