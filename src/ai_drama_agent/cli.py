"""命令行入口。"""

from __future__ import annotations

import argparse
from pathlib import Path

from .models import GenerationOptions
from .pipeline import build_default_agent, write_outputs


def main() -> None:
    parser = argparse.ArgumentParser(description="将 AI 漫剧剧本转换为制作包。")
    parser.add_argument("--script", required=True, help="剧本文本文件路径。")
    parser.add_argument("--output", required=True, help="输出目录。")
    parser.add_argument("--title", default="未命名 AI 漫剧")
    parser.add_argument("--style", default="电影感二维国漫，细腻光影")
    parser.add_argument("--aspect-ratio", default="16:9")
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--target-model", default="model-agnostic")
    parser.add_argument("--offline-demo", action="store_true")
    args = parser.parse_args()

    script_path = Path(args.script)
    script = script_path.read_text(encoding="utf-8")
    options = GenerationOptions(
        title=args.title,
        visual_style=args.style,
        aspect_ratio=args.aspect_ratio,
        fps=args.fps,
        target_model=args.target_model,
    )
    project = build_default_agent(offline_demo=args.offline_demo).run(script, options)
    output_dir = Path(args.output)
    write_outputs(project, output_dir)
    print(f"已生成 AI 漫剧制作包：{output_dir.resolve()}")
    print(f"角色：{len(project.characters)}，场景：{len(project.scenes)}，镜头：{len(project.shots)}")
    print(f"连续性问题：{len(project.continuity_issues)}")


if __name__ == "__main__":
    main()
