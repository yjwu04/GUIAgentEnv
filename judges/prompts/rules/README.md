这是目前的judge prompt模版，会不断更新
# yaml

- judge_role: "e.g., robustness"
- version: e.g., 1.0 识别是否修改过prompt

- template:
  - context:
    - Attribute 1:...
  - system_prompt:
    - role:
    - rules:
  - output_format:
    - type: json
    - json_schema:
