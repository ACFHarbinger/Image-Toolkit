import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import MarkdownIt from 'markdown-it';
import { FileText, ChevronRight } from 'lucide-react';
import mermaid from 'mermaid';

mermaid.initialize({ startOnLoad: false, theme: 'dark' });

const md = new MarkdownIt({ html: true, linkify: true, typographer: true });

const DOC_PAGES = [
  { id: 'index.md', title: 'Overview' },
  { id: 'ARCHITECTURE.md', title: 'Architecture' },
  { id: 'BENCHMARKS.md', title: 'Benchmarks' },
  { id: 'CHANGELOG.md', title: 'Changelog' },
  { id: 'DEPENDENCY_POLICY.md', title: 'Dependency Policy' },
  { id: 'DEVELOPMENT.md', title: 'Development' },
  { id: 'DOCUMENTATION_STANDARDS.md', title: 'Documentation Standards' },
  { id: 'GLOSSARY.md', title: 'Glossary' },
  { id: 'SECURITY.md', title: 'Security' },
  { id: 'TESTING.md', title: 'Testing' },
  { id: 'TROUBLESHOOTING.md', title: 'Troubleshooting' }
];

export default function Docs() {
  const { fileId } = useParams<{ fileId: string }>();
  const activeFile = fileId || 'index.md';
  const [content, setContent] = useState<string>('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetch(`/docs/${activeFile}`)
      .then(res => {
        if (!res.ok) throw new Error('Failed to load document');
        return res.text();
      })
      .then(text => {
        setContent(md.render(text));
        setLoading(false);
      })
      .catch(err => {
        setContent(`<h1>Error</h1><p>${err.message}</p>`);
        setLoading(false);
      });
  }, [activeFile]);

  useEffect(() => {
    if (!loading) {
      const els = document.querySelectorAll('.prose pre code.language-mermaid');
      els.forEach((el, index) => {
        const parent = el.parentElement;
        if (parent) {
          const div = document.createElement('div');
          div.className = 'mermaid my-8 p-4 bg-[#0a0a0c] border border-[#1a1c23] rounded-lg flex justify-center';
          div.id = `mermaid-${index}`;
          div.textContent = el.textContent;
          parent.replaceWith(div);
        }
      });
      mermaid.run({ querySelector: '.mermaid' }).catch(console.error);
    }
  }, [loading, content]);

  return (
    <div className="max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-[250px_1fr] gap-8 py-12 px-8 min-h-screen pt-32">
      {/* Sidebar */}
      <aside className="hud-panel h-fit sticky top-32">
        <div className="flex items-center gap-2 mb-6 pb-4 border-b border-[rgba(0,240,255,0.2)]">
          <FileText className="w-5 h-5 text-[#00f0ff]" />
          <h2 className="font-bold text-lg text-[#00F0FF]" style={{fontFamily: 'Chakra Petch'}}>Documentation</h2>
        </div>
        <nav className="space-y-2">
          {DOC_PAGES.map(page => (
            <Link 
              key={page.id} 
              to={`/docs/${page.id}`}
              className={`flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-colors ${activeFile === page.id ? 'bg-[rgba(0,240,255,0.15)] text-[#00f0ff] font-bold border border-[#00f0ff]' : 'text-[#8c92a0] hover:bg-[rgba(0,240,255,0.05)] hover:text-[#00F0FF]'}`}
            >
              {page.title}
              {activeFile === page.id && <ChevronRight className="w-4 h-4" />}
            </Link>
          ))}
        </nav>
      </aside>

      {/* Main Content */}
      <main className="hud-panel md:p-12">
        {loading ? (
          <div className="flex items-center justify-center h-64">
            <div className="w-8 h-8 rounded-full border-4 border-[#00f0ff]/30 border-t-[#00f0ff] animate-spin" />
          </div>
        ) : (
          <div 
            className="prose prose-invert max-w-none prose-a:text-[#00f0ff] hover:prose-a:text-[#ff0055] prose-code:bg-[#1a1c23] prose-code:text-[#00f0ff] prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded-md prose-pre:bg-[#050505] prose-pre:border prose-pre:border-[#1a1c23]"
            dangerouslySetInnerHTML={{ __html: content }} 
          />
        )}
      </main>
    </div>
  );
}
