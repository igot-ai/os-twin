import os
import re

directory = '/mnt/e/OS Twin/os-twin/dashboard/fe/src'

replacements = {
    r'bg-white\b': 'bg-surface',
    r'bg-slate-50\b': 'bg-surface-hover',
    r'bg-slate-100\b': 'bg-surface-alt',
    r'bg-slate-200\b': 'bg-border',
    r'bg-slate-800\b': 'bg-surface',
    r'bg-slate-900\b': 'bg-background-dark',
    r'bg-slate-900/60\b': 'bg-background-dark/60',
    r'text-slate-900\b': 'text-text-main',
    r'text-slate-800\b': 'text-text-main',
    r'text-slate-700\b': 'text-text-main',
    r'text-slate-600\b': 'text-text-muted',
    r'text-slate-500\b': 'text-text-muted',
    r'text-slate-400\b': 'text-text-faint',
    r'text-slate-300\b': 'text-text-faint',
    r'border-slate-100\b': 'border-border-light',
    r'border-slate-200\b': 'border-border',
    r'border-slate-300\b': 'border-border',
    r'bg-blue-50\b': 'bg-primary-light',
    r'bg-blue-100\b': 'bg-primary-muted',
    r'bg-blue-500\b': 'bg-primary',
    r'bg-blue-600\b': 'bg-primary',
    r'text-blue-500\b': 'text-primary',
    r'text-blue-600\b': 'text-primary',
    r'text-blue-700\b': 'text-primary-hover',
    r'text-blue-800\b': 'text-primary-hover',
    r'text-blue-900\b': 'text-primary-hover',
    r'border-blue-100\b': 'border-primary-light',
    r'border-blue-200\b': 'border-primary-muted',
    r'border-blue-500\b': 'border-primary',
    r'ring-blue-500\b': 'ring-primary',
    r'bg-green-50\b': 'bg-success-light',
    r'bg-green-100\b': 'bg-success-light',
    r'text-green-500\b': 'text-success',
    r'text-green-600\b': 'text-success',
    r'text-green-700\b': 'text-success-text',
    r'border-green-500\b': 'border-success',
    r'bg-red-50\b': 'bg-danger-light',
    r'bg-red-100\b': 'bg-danger-light',
    r'text-red-500\b': 'text-danger',
    r'text-red-600\b': 'text-danger',
    r'border-red-500\b': 'border-danger',
    r'bg-yellow-50\b': 'bg-warning-light',
    r'text-yellow-600\b': 'text-warning',
    r'text-yellow-700\b': 'text-warning-text',
    r'border-yellow-200\b': 'border-warning/50',
    r'bg-amber-50\b': 'bg-warning-light',
    r'text-amber-600\b': 'text-warning',
    r'text-amber-700\b': 'text-warning-text',
    r'border-amber-200\b': 'border-warning/50',
    r'bg-orange-50\b': 'bg-warning-light',
    r'text-orange-700\b': 'text-warning-text',
    r'border-orange-500\b': 'border-warning',
    r'bg-purple-50\b': 'bg-primary-muted',
    r'text-purple-700\b': 'text-primary',
    r'border-purple-500\b': 'border-primary',
}

for root, _, files in os.walk(directory):
    for file in files:
        if file.endswith('.tsx') or file.endswith('.ts'):
            path = os.path.join(root, file)
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            new_content = content
            for old, new in replacements.items():
                new_content = re.sub(old, new, new_content)
                
            if new_content != content:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"Updated {path}")
