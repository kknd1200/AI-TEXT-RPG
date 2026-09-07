"""Assemble reviewed generated raster frames; never draw or recolor artwork."""
import argparse, hashlib, json, zipfile, tarfile
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'art-source/cre36'
PUBLIC=ROOT/'public/assets/cre36'
ACTIONS=('idle','feed','mist','clean','play')
STAGES=('baby','adult')

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--partial',action='store_true',help='Local review only; never ship this result.')
    args=parser.parse_args()
    identities=json.loads((ART/'spec-v2.json').read_text())['identities']
    manifest={'schemaVersion':1,'artSource':'built-in image_gen','cellSize':96,'logicalCellSize':48,'columns':8,'rows':5,'actions':list(ACTIONS),'stages':list(STAGES),'frameDurationMs':240,'forms':[],'complete':False}
    (PUBLIC/'atlases').mkdir(exist_ok=True)
    missing=[]
    quality=[]
    for morph,name,_ in identities:
        atlas=Image.new('RGBA',(768,480))
        for stage_index,stage in enumerate(STAGES):
            form={'id':morph+'-'+stage,'morphId':morph,'stage':stage,'sheet':f'/assets/cre36/atlases/{morph}.png','animations':{}}
            for row,action in enumerate(ACTIONS):
                path=PUBLIC/morph/stage/(action+'.png')
                if not path.exists():
                    missing.append(str(path.relative_to(ROOT)))
                    continue
                sheet=Image.open(path).convert('RGBA')
                frames=[sheet] if action=='idle' else [sheet.crop(((i%2)*96,(i//2)*96,(i%2+1)*96,(i//2+1)*96)) for i in range(4)]
                hashes=[]
                for index,frame in enumerate(frames):
                    assert frame.size==(96,96),path
                    bounds=frame.getchannel('A').getbbox()
                    assert bounds and bounds[0]>0 and bounds[1]>0 and bounds[2]<96 and bounds[3]<96,(path,bounds)
                    atlas.paste(frame,((stage_index*4+index)*96,row*96))
                    hashes.append(hashlib.sha256(frame.tobytes()).hexdigest())
                if action!='idle':
                    assert len(set(hashes))==4,'Duplicate animation poses: '+str(path)
                    record=json.loads((ART/'qc'/morph/stage/action/'record.json').read_text())
                    qc=json.loads((ART/'qc'/morph/stage/action/'pipeline-meta.json').read_text())
                    quality.append({**record,'uniqueFrames':len(set(hashes)),'frameSha256':hashes,'qc':qc['qc_summary'],'edgeTouchFrames':qc['edge_touch_frames'],'emptyFrames':qc['empty_frames'],'clampedFrames':qc['paste_clamped_frames']})
                form['animations'][action]={'row':row,'startColumn':stage_index*4,'frames':len(frames),'frameSha256':hashes}
                if action=='idle':
                    # Exact requested standalone dimensions; retain the coarse
                    # generated pixels, shared center and safe bottom padding.
                    size=128 if stage=='baby' else 160
                    standalone=Image.new('RGBA',(size,size))
                    standalone.paste(frames[0],((size-96)//2,size-100))
                    folder=ROOT/'public/assets/geckos'/stage
                    folder.mkdir(parents=True,exist_ok=True)
                    filename=f'{morph}_{stage}.png'
                    standalone.save(folder/filename,optimize=True)
                    form['portrait']=f'/assets/geckos/{stage}/{filename}'
                    form['portraitSize']=size
            manifest['forms'].append(form)
        atlas_path=PUBLIC/'atlases'/f'{morph}.png'
        atlas.save(atlas_path,optimize=True)
        atlas_hash=hashlib.sha256(atlas_path.read_bytes()).hexdigest()
        for form in manifest['forms'][-2:]:
            form['sheetSha256']=atlas_hash
    if missing and not args.partial:
        raise SystemExit('Incomplete sprites: '+str(len(missing))+' files.\n'+'\n'.join(missing[:12]))
    manifest['missingFiles']=missing
    manifest['missingEffects']=[a for a in ACTIONS[1:] if not (PUBLIC/'fx'/f'{a}.png').exists()]
    manifest['complete']=not args.partial and not missing and not manifest['missingEffects']
    (PUBLIC/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    (ART/'quality-report.json').write_text(json.dumps(quality,ensure_ascii=False,indent=2)+'\n')
    prompts={p.stem:p.read_text() for p in sorted((ART/'prompts').glob('*.txt'))}
    (ART/'prompts.json').write_text(json.dumps(prompts,ensure_ascii=False,indent=2)+'\n')
    if manifest['complete']:
        with zipfile.ZipFile(PUBLIC/'cre36-sprites.zip','w',zipfile.ZIP_DEFLATED) as archive:
            archive.write(PUBLIC/'manifest.json','manifest.json')
            for p in sorted((PUBLIC/'atlases').glob('*.png')):
                archive.write(p,'atlases/'+p.name)
            for p in sorted(PUBLIC.glob('cre_*/*/*.gif')):
                archive.write(p,str(p.relative_to(PUBLIC)))
            archive.write(ART/'prompts.json','prompts.json')
    # Keep the generated PNG set as one source-controlled binary bundle.
    # The build restores the same files before checking the release manifest.
    paths=sorted((PUBLIC/'atlases').glob('*.png'))+sorted((ROOT/'public/assets/geckos').glob('*/*.png'))+sorted((PUBLIC/'fx').glob('*.png'))
    with tarfile.open(ART/'runtime-sprites.tar.gz','w:gz',format=tarfile.USTAR_FORMAT) as bundle:
        for path in paths:bundle.add(path,arcname=str(path.relative_to(ROOT)),recursive=False)
    print(json.dumps({'forms':len(manifest['forms']),'stageActions':len(quality),'missingFiles':len(missing),'missingEffects':manifest['missingEffects'],'complete':manifest['complete']},ensure_ascii=False))

if __name__=='__main__':main()
