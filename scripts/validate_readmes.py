"""Check local links and the shared onboarding/feature contract in three languages."""
from pathlib import Path
import json
import re
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
FILES = ('README.md', 'README.pt-BR.md', 'README.es.md')


def anchors(text):
    found, counts = set(), {}
    for title in re.findall(r'^#{1,6}\s+(.+)$', text, re.M):
        slug = re.sub(r'[^\w\- ]', '', title.lower()).replace(' ', '-')
        count = counts.get(slug, 0)
        found.add(slug + (f'-{count}' if count else ''))
        counts[slug] = count + 1
    return found


def main():
    agents = json.loads((ROOT / 'manifest.json').read_text(encoding='utf-8'))['specialist_agents']
    for name in FILES:
        text = (ROOT / name).read_text(encoding='utf-8')
        assert text.count('```') % 2 == 0, f'{name}: unbalanced code fences'
        assert text.count('<details>') == text.count('</details>'), f'{name}: unbalanced details'
        for required in (*FILES, *agents, 'uvx ai-dlc-engineering-os setup', 'AI_DLC_GRAPH_ROOTS',
                         'index_repository_graph', 'repository_graph_status', 'query_repository_graph',
                         'docs/REPOSITORY_GRAPH.md', 'docs/assets/ai-dlc-social-preview.jpg'):
            assert required in text, f'{name}: missing {required}'
        assert 'agentshield.com.br' not in text and 'by AgentShield' not in text, name
        urls = re.findall(r'\]\(([^\s)]+)\)', text) + re.findall(r'<img[^>]+src="([^"]+)"', text)
        for url in urls:
            if re.match(r'^[a-z]+:', url):
                continue
            path, _, fragment = unquote(url).partition('#')
            target = ROOT / (path or name)
            assert target.exists(), f'{name}: missing link {url}'
            if fragment and target.suffix == '.md':
                assert fragment in anchors(target.read_text(encoding='utf-8')), f'{name}: missing anchor {url}'
    print('README validation passed: EN/PT-BR/ES links, anchors, onboarding, agents and graph contract.')


if __name__ == '__main__':
    main()
