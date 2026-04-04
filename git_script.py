import subprocess

try:
    out = subprocess.check_output(["git", "show", "HEAD~1:dashboard/fe/src/components/ui/SearchModal.tsx"], cwd="/mnt/e/OS Twin/os-twin").decode('utf-8')
    with open("/mnt/e/OS Twin/os-twin/search_modal_old.tsx", "w") as f:
        f.write(out)
except Exception as e:
    print(e)
