import os
import glob
import pandas as pd
import bm25s
from copy import deepcopy
from bm25s.tokenization import Tokenizer
from transformers import AutoTokenizer


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
tokenizer = AutoTokenizer.from_pretrained(os.path.join(BASE_DIR, "tokenizer"))

def cut_word(text):
    # return list(jieba.cut(text))
    tokens = tokenizer.encode(text, add_special_tokens=False)
    return [tokenizer.decode(token) for token in tokens]


cities = {
    "beijing": "北京",
    "chengdu": "成都",
    "chongqing": "重庆",
    "guangzhou": "广州",
    "hangzhou": "杭州",
    "nanjing": "南京",
    "shanghai": "上海",
    "shenzhen": "深圳",
    "suzhou": "苏州",
    "wuhan": "武汉",
}
targets = ["accommodations", "attractions", "restaurants"]
database_path = f"{BASE_DIR}/../ChinaTravel/chinatravel/environment/database"

def build_corpus():
    for k, v in cities.items():
        for kind in targets:
            corpus = []
            p1 = os.path.join(database_path, kind)
            p2 = os.path.join(p1, k)
            files = glob.glob(os.path.join(p2, "*.csv"))
            for file in files:
                csv = pd.read_csv(file)
                for row in csv.iterrows():
                    data = row[1].to_dict()
                    corpus.append(data['name'])
            tokenizer = Tokenizer(splitter=cut_word)
            corpus_tokens = tokenizer.tokenize(corpus, return_as="tuple")
            retriever = bm25s.BM25(corpus=corpus,)
            retriever.index(corpus_tokens)
            retriever.save(f"corpus/{k}_{kind}")
            tokenizer.save_vocab(save_dir=f"corpus/{k}_{kind}")


def load():
    results = {}
    corpus_dir = os.path.join(BASE_DIR, "corpus")
    for city in cities:
        results[city] = {}
        for kind in targets:
            path = os.path.join(corpus_dir, f"{city}_{kind}")
            retriever = bm25s.BM25.load(path, load_corpus=True)
            corpus = [item["text"] for item in retriever.corpus]
            tokenizer = Tokenizer(splitter=cut_word)
            tokenizer.load_vocab(path)
            results[city][kind] = {
                "retriever": retriever,
                "tokenizer": tokenizer,
                "corpus": corpus
            }
    return results

class BM25Retriever:
    def __init__(self, ):
        self.corpus_tokenizer_map = load()
        self.city_rev_map = {v : k for k, v in cities.items()}
        self.city_map = cities

    def retrieval_all(self, nature_language_constraints, topk=10):
        target_city = self.city_rev_map[nature_language_constraints["target_city"]]
        subset = self.corpus_tokenizer_map[target_city]
        keys = ["must_attraction_name", "must_accommodation_name", "must_restaurant_name"]
        result = deepcopy(nature_language_constraints)
        for key in keys:
            subsubset = subset[key.split("_")[1] + "s"]
            retriever = subsubset["retriever"]
            tokenizer = subsubset["tokenizer"]
            corpus = subsubset["corpus"]
            qs = nature_language_constraints.get(key, [])
            rqs = []
            if qs == []:
                continue
            for q in qs:
                if q in corpus:
                    rqs.append(q)
                else:
                    query_tokens = tokenizer.tokenize([q], update_vocab=False)
                    results, scores = retriever.retrieve(query_tokens, k=topk)
                    ranked_results = self.rerank(results, scores)
                    rq = ranked_results[0]["text"]
                    rqs.append(rq)
            print(f"before {qs}\nafter {rqs}")
            result[key] = rqs
        return result
    
    
    def retrieval(self, kind, queries, target_city, topk=10):
        try:
            assert kind in targets
            if target_city in self.corpus_tokenizer_map:
                subset = self.corpus_tokenizer_map[target_city]
            else:
                subset = self.corpus_tokenizer_map[self.city_rev_map[target_city]]
            subsubset = subset[kind]
            retriever = subsubset["retriever"]
            tokenizer = subsubset["tokenizer"]
            corpus = subsubset["corpus"]
            if queries == []:
                return []
            if isinstance(queries, list):
                rqs = []
                for q in queries:
                    if q in corpus:
                        rqs.append(q)
                    else:
                        query_tokens = tokenizer.tokenize([q], update_vocab=False)
                        results, scores = retriever.retrieve(query_tokens, k=topk)
                        ranked_results = self.rerank(results, scores)
                        rq = ranked_results[0]["text"]
                        rqs.append(rq)
                return rqs
            else:
                if queries in corpus:
                    return queries
                else:
                    query_tokens = tokenizer.tokenize([queries], update_vocab=False)
                    results, scores = retriever.retrieve(query_tokens, k=topk)
                    ranked_results = self.rerank(results, scores)
                    rq = ranked_results[0]["text"]
                    return rq
        except:
            return queries

    def rerank(self, results, scores, interval=1.0):
        start = scores[0][0]
        end = start - interval
        ranked_results = []
        for result, score in zip(results[0], scores[0]):
            if score >= end:
                ranked_results.append(result)
            else:
                break
                
        ranked_results.sort(key=lambda x: x["id"])
        return ranked_results



if __name__ == "__main__":
    build_corpus()
