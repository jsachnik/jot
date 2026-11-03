"""Tiny offline text matching (TF-IDF + cosine). No libraries, no AI.

Powers offline search, "ideas like this one", suggested links and the
offline librarian.
"""

import math
import re
from collections import Counter

STOP = set("""a an the and or but if of to in on at for with without from by as is are was were be been being it its
this that these those i me my we our you your he she they them his her their there here what which who whom how why
when where do does did done doing have has had having not no so than too very can could should would will just about
into over under again more most some such only own same then once also up down out off all any both each few other
idea ideas maybe like get got make made use using used want try one two""".split())


def stem(w):
    for suf in ("ingly", "ing", "edly", "ed", "es", "s", "ly"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[: -len(suf)]
    return w


def tokens(text):
    out = []
    for w in re.findall(r"[^\W_]{2,}", (text or "").lower()):
        if w in STOP:
            continue
        out.append(stem(w))
    return out


class Index:
    """docs: {id: text}. Title/group words should be repeated by the caller to weight them."""

    def __init__(self, docs):
        self.tf = {i: Counter(tokens(t)) for i, t in docs.items()}
        self.n = max(len(docs), 1)
        df = Counter()
        for c in self.tf.values():
            df.update(c.keys())
        self.idf = {w: math.log(1 + self.n / d) for w, d in df.items()}
        self.vec = {i: self._norm(c) for i, c in self.tf.items()}

    def _norm(self, counter):
        v = {w: (1 + math.log(c)) * self.idf.get(w, math.log(1 + self.n)) for w, c in counter.items()}
        mag = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {w: x / mag for w, x in v.items()}

    @staticmethod
    def _dot(a, b):
        if len(a) > len(b):
            a, b = b, a
        return sum(x * b.get(w, 0.0) for w, x in a.items())

    def query(self, text, k=8, exclude=()):
        q = self._norm(Counter(tokens(text)))
        if not q:
            return []
        scored = [(i, self._dot(q, v)) for i, v in self.vec.items() if i not in exclude]
        scored = [s for s in scored if s[1] > 0.04]
        scored.sort(key=lambda s: -s[1])
        return scored[:k]

    def similar(self, idea_id, k=6):
        base = self.vec.get(idea_id)
        if not base:
            return []
        scored = [(i, self._dot(base, v)) for i, v in self.vec.items() if i != idea_id]
        scored = [s for s in scored if s[1] > 0.05]
        scored.sort(key=lambda s: -s[1])
        return scored[:k]

    def shared_words(self, a, b, limit=4):
        va, vb = self.vec.get(a, {}), self.vec.get(b, {})
        common = sorted(set(va) & set(vb), key=lambda w: -(va[w] * vb[w]))
        return common[:limit]
