from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
ROOT=Path(__file__).resolve().parents[1]
def search_policy(query,top_k=2):
    raw=(ROOT/"knowledge_base"/"student_handbook.md").read_text(encoding="utf-8")
    sections=[]
    heading="General"; lines=[]
    for line in raw.splitlines():
        if line.startswith("#"):
            if lines: sections.append((heading," ".join(lines)))
            heading=line.lstrip("# ").strip(); lines=[]
        elif line.strip(): lines.append(line.strip())
    if lines: sections.append((heading," ".join(lines)))
    if not sections:return []
    docs=[h+" "+t for h,t in sections]
    v=TfidfVectorizer(stop_words="english",ngram_range=(1,2))
    m=v.fit_transform(docs+[query]); scores=cosine_similarity(m[-1],m[:-1]).ravel()
    ranked=sorted(zip(scores,sections),reverse=True,key=lambda x:x[0])
    return [{"chunk_id":f"POL-{i+1:02d}","heading":h,"text":t,"score":round(float(s),3)} for i,(s,(h,t)) in enumerate(ranked[:top_k]) if s>0]
