"""Local deployment setup; never installs or mutates ERPNext."""
import argparse,json,os,sqlite3
from pathlib import Path
from cryptography.fernet import Fernet

def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['init','backup']);p.add_argument('--directory',default='.');p.add_argument('--output');a=p.parse_args();root=Path(a.directory).resolve()
    if a.command=='init':
        root.mkdir(parents=True,exist_ok=True);target=root/'.env'
        content='HEC_MASTER_KEY='+Fernet.generate_key().decode()+'\nHEC_DATA_DIR='+str(root/'data')+'\nHEC_ERP_ORIGIN=https://erptest.wahatalhaitham.com\nHEC_ERP_HOSTS=erptest.wahatalhaitham.com\nHEC_TIMEZONE=Asia/Aden\n'
        fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as f:f.write(content)
        print('Created protected environment file:',target)
    else:
        if not a.output:p.error('--output required')
        # An SQLite-consistent backup; copy media and protected .env separately.
        source=root/'data/store.db';dest=Path(a.output)
        if dest.exists():p.error('Output already exists')
        with sqlite3.connect(source) as src,sqlite3.connect(dest) as out:src.backup(out)
        os.chmod(dest,0o600);print('Database backup created:',dest)
if __name__=='__main__':main()
