"""Exact b948879 pre-O_NOATIME Gateway method; no imports/ROS execution."""
def _export_controller_records(self):
        # This is a C-side source. Only actual delivered flow95 reaches R runtime.
        path=self.directory/"controller/allocation-events.jsonl"
        if not path.exists() or self.wires is None:return
        with path.open() as stream:
            stream.seek(self.journal_position)
            while True:
                position=stream.tell();line=stream.readline()
                if not line or not line.endswith("\n"):
                    self.journal_position=position;return
                row=json.loads(line)
                if row.get("kind") in ("rl_actual_nav2_goal_request","rl_actual_nav2_goal_response","rl_actual_nav2_goal_result","rl_halt_requested"):
                    self.journal_pub.publish(String(data=line.rstrip("\n")))
