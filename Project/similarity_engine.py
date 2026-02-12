from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import pandas as pd


def compute_similarity(text_list, document_names=None):


    if len(text_list) < 2:
        raise ValueError("Need at least 2 documents to compute similarity.")

    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform(text_list)

    similarity_matrix = cosine_similarity(tfidf_matrix)

    if not document_names:
        document_names = [f"Doc{i+1}" for i in range(len(text_list))]

    similarity_df = pd.DataFrame(
        similarity_matrix,
        index=document_names,
        columns=document_names
    )

    return similarity_df