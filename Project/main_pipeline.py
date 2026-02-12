from ocr_module import extract_text_from_image
from nlp_module import clean_text
from similarity_engine import compute_similarity
import numpy as np


def get_verdict(percentage):
    if 0 <= percentage <= 60:
        return "Unique Documents"
    elif 61 <= percentage <= 75:
        return "Partially Copied (Manual Intervention Required)"
    elif 76 <= percentage <= 100:
        return "Totally Copied"
    else:
        return "Invalid Score"


def run_pipeline(file_paths):

    cleaned_texts = []
    doc_names = []

    for file_path in file_paths:
        print(f"\nProcessing: {file_path}")

        raw_text = extract_text_from_image(file_path)
        processed_text = clean_text(raw_text)

        cleaned_texts.append(processed_text)
        doc_names.append(file_path.split("/")[-1])

    similarity_df = compute_similarity(cleaned_texts, doc_names)

    return similarity_df


if __name__ == "__main__":

    files = [
        r"C:\Users\wwwve\Documents\CodeFiles\CSE 4 2 ML Project\Datasets\Handwritten\Copied\Student A.png",
        r"C:\Users\wwwve\Documents\CodeFiles\CSE 4 2 ML Project\Datasets\Handwritten\Copied\Student B.png",
      
    ]

    result = run_pipeline(files)

    print("\n================ SIMILARITY MATRIX (%) ================")
    percentage_matrix = result * 100
    print(percentage_matrix.round(2))
    print("========================================================")

    similarity_values = percentage_matrix.values
    upper_triangle = similarity_values[np.triu_indices(len(similarity_values), k=1)]

    if len(upper_triangle) == 0:
        print("\nNot enough documents for comparison.")
    else:
        average_similarity = round(np.mean(upper_triangle), 2)
        final_verdict = get_verdict(average_similarity)

        print("\n================ FINAL VERDICT ================")
        print(f"Average Similarity : {average_similarity}%")
        print(f"Overall Verdict    : {final_verdict}")
        print("==============================================\n")


