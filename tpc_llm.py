
import os
import sys
import re
import repair_json
from vllm import LLM, SamplingParams
from transformers import AutoTokenizer, AutoConfig

project_root_path = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
if project_root_path not in sys.path:
    sys.path.append(project_root_path)
if os.path.dirname(project_root_path) not in sys.path:
    sys.path.append(os.path.dirname(project_root_path))

from agent.llms import AbstractLLM


class TPCLLM(AbstractLLM):
    def __init__(self):
        super().__init__()
        
        model_name="qwen3-8B"
        max_model_len=32768
        project_root_path = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        
        self.path = os.path.join(
            project_root_path, "agent/tpc_agent/"+model_name
        )
        os.environ["VLLM_ALLOW_LONG_MAX_MODEL_LEN"] = "1" 
        
        self.sampling_params = SamplingParams(
            temperature=1.0, 
            top_p=0.95, 
            top_k=20, 
            max_tokens=4096
        )
            
        if max_model_len is not None and max_model_len > 32768:
            config = AutoConfig.from_pretrained(self.path)
            config.rope_scaling = {
                "type": "yarn", 
                "factor": max_model_len // 32768,
                "original_max_position_embeddings": 32768
            }
            config.save_pretrained(self.path)
            os.environ["VLLM_ALLOW_LONG_MAX_MODEL_LEN"] = "1"
        else:
            config = AutoConfig.from_pretrained(self.path)
            if "rope_scaling" in config.to_dict():
                del config.rope_scaling
            config.save_pretrained(self.path)

        self.tokenizer = AutoTokenizer.from_pretrained(self.path)

        if max_model_len is None:
            max_model_len = 32768
            
        self.llm = LLM(
            model=self.path,
            gpu_memory_utilization=0.95,
            max_model_len=max_model_len,
            enable_prefix_caching=(max_model_len >= 32768),
        )

        self.name = model_name
        self.max_model_len = max_model_len

    def _get_response(self, messages, one_line, json_mode):
        text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=True
        )

        input_tokens = self.tokenizer(text)["input_ids"]
        self.input_token_count += len(input_tokens)       
        self.input_token_maxx = max(self.input_token_maxx, len(input_tokens))
        
        if len(input_tokens) >= self.max_model_len:
            return str({"error": f"Input prompt is longer than {self.max_model_len} tokens."})
        outputs = self.llm.generate([text], self.sampling_params)


        generated_text = outputs[0].outputs[0].text

        output_token_ids = outputs[0].outputs[0].token_ids
        self.output_token_count += len(output_token_ids)

        try:
            m = re.match(r"<think>\n(.+)</think>\n\n", generated_text, flags=re.DOTALL)
            content = generated_text[len(m.group(0)):]
            thinking_content = m.group(1).strip()

        except Exception as e:
            thinking_content = ""
            content = generated_text.strip()
        
        res_str = content
        try:
            if json_mode:
                res_str = repair_json(res_str, ensure_ascii=False)
            elif one_line:
                res_str = res_str.split("\n")[0]
        except Exception as e:
            res_str = '{"error": "Request with specific format failed, please try again."}'
        return res_str