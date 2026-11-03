"""Debounced arrivals. Presence is not speaker identification."""
class ArrivalPolicy:
    def __init__(self):
        self.active = set()
        self.first_seen = {}
        self.last_seen = {}
        self.last_greeting = float('-inf')

    def observe(self, snapshot, now, cooldown=600, allowed=True):
        keys = set(snapshot.get('present', [])) if snapshot.get('status') == 'running' else set()
        if snapshot.get('status') == 'running' and snapshot.get('face_count', 0) > len(keys):
            keys.add('visitor')
        for key in keys:
            self.first_seen.setdefault(key, now)
            self.last_seen[key] = now
        for key in list(self.last_seen):
            if key not in keys and now - self.last_seen[key] >= 15:
                self.active.discard(key)
                self.first_seen.pop(key, None)
                self.last_seen.pop(key, None)
        ready = {key for key in keys if now - self.first_seen[key] >= 3}
        arrivals = ready - self.active
        if not allowed:
            # Don't greet people who arrived while paused or mid-conversation later.
            self.active.update(ready)
            return False
        if arrivals and now - self.last_greeting >= cooldown:
            self.active.update(ready)
            self.last_greeting = now
            return True
        self.active.update(ready)
        return False
