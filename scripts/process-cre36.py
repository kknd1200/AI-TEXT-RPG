"""Deterministic sprite extraction only. Raw artwork is made by image_gen.

The generate2dsprite processor supplies chroma keying, anchoring and QC.
Nearest-neighbor sampling preserves the requested coarse pixel grid.
"""
import argparse, contextlib, hashlib, importlib.util, io, json, os
from pathlib import Path
from PIL import Image

def accelerate_processor(processor):
    """Identical masks/components, using compiled array operations when available."""
    try:
        import numpy as np
        from scipy import ndimage
    except ImportError:
        return
    def key_magenta(image, threshold=100, edge_threshold=150):
        data=np.array(image)
        rgb=data[:,:,:3].astype('int32')
        distance=((rgb-np.array([255,0,255]))**2).sum(axis=2)
        near=distance<threshold**2
        data[near]=0
        traversable=(data[:,:,3]==0)|(distance<edge_threshold**2)
        seed=np.zeros(traversable.shape,dtype=bool)
        seed[0,:]=traversable[0,:]; seed[-1,:]=traversable[-1,:]
        seed[:,0]=traversable[:,0]; seed[:,-1]=traversable[:,-1]
        outside=ndimage.binary_propagation(seed,structure=np.ones((3,3)),mask=traversable)
        data[outside&(data[:,:,3]>0)]=0
        # Remove magenta matte spill at the alpha edge without recoloring the
        # morph: use the nearest uncontaminated opaque source pixel.
        opaque=data[:,:,3]>0
        rgb=data[:,:,:3].astype('int32')
        spill=opaque&(rgb[:,:,0]>rgb[:,:,1]+30)&(rgb[:,:,2]>rgb[:,:,1]+30)&(rgb[:,:,1]<0.5*np.minimum(rgb[:,:,0],rgb[:,:,2]))
        spill &= ndimage.binary_dilation(~opaque,iterations=2)
        good=opaque&~spill
        if spill.any() and good.any():
            nearest=ndimage.distance_transform_edt(~good,return_distances=False,return_indices=True)
            recovered=data[nearest[0],nearest[1],:3]
            data[spill,:3]=recovered[spill]
        return Image.fromarray(data)
    def components(image,min_area=1):
        mask=np.asarray(image.getchannel('A'))>0
        labels,count=ndimage.label(mask)
        sizes=np.bincount(labels.ravel())
        found=[]
        for label,box in enumerate(ndimage.find_objects(labels),start=1):
            if box is None or sizes[label]<min_area: continue
            y,x=box
            found.append({'area':int(sizes[label]),'bbox':(x.start,y.start,x.stop,y.stop),'touches_edge':x.start==0 or y.start==0 or x.stop==image.width or y.stop==image.height})
        return sorted(found,key=lambda item:item['area'],reverse=True)
    processor.remove_bg_magenta=key_magenta
    processor.connected_components=components

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'art-source/cre36'
PUBLIC = ROOT / 'public/assets/cre36'
STAGES = ('baby', 'adult')
ACTIONS = ('feed', 'mist', 'clean', 'play')
CELL = 48
PROCESSOR_VERSION = 4

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--processor', default=os.environ.get('CRE_SPRITE_PROCESSOR', '/root/.codex/skills/remote-skills/skill-6a7d043e43588191b8b940b2d07db776/scripts/generate2dsprite.py'))
    parser.add_argument('--ids', nargs='*')
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location('sprite_processor', args.processor)
    processor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(processor)
    accelerate_processor(processor)
    original_resize = Image.Image.resize
    def pixel_resize(self, size, resample=None, box=None, reducing_gap=None):
        return original_resize(self, size, Image.Resampling.NEAREST, box, reducing_gap)
    Image.Image.resize = pixel_resize
    original_anchor = processor.estimate_anchor
    def centered_anchor(frame, bbox, align):
        anchor = original_anchor(frame, bbox, align)
        # Lifting one foot must not shift the entire character sideways.
        return (frame.width/2, anchor[1]) if anchor else None
    processor.estimate_anchor = centered_anchor
    count = 0
    failures = []
    for raw in sorted((ART/'raw').glob('cre_*-*.png'),key=lambda p:(p.stem.split('-')[0],ACTIONS.index(p.stem.split('-')[1]))):
        morph, action = raw.stem.split('-')
        if action not in ACTIONS or (args.ids and morph not in args.ids):
            continue
        source_hash = hashlib.sha256(raw.read_bytes()).hexdigest()
        image = Image.open(raw).convert('RGBA')
        for stage_index, stage in enumerate(STAGES):
            out = PUBLIC/morph/stage
            qc = ART/'qc'/morph/stage/action
            record_path = qc/'record.json'
            if not args.force and record_path.exists():
                previous = json.loads(record_path.read_text())
                if previous['sourceSha256'] == source_hash and previous.get('processorVersion') == PROCESSOR_VERSION:
                    continue
            qc.mkdir(parents=True, exist_ok=True)
            half = image.height//2
            crop_path = qc/'source-grid.png'
            image.crop((0, stage_index*half, image.width, (stage_index+1)*half)).save(crop_path)
            profile = ART/'qc'/morph/stage/'scale-profile.json'
            # A shared four-pixel foot margin also contains the feeding tongue.
            # This is one uniform scale for all poses and every grounded action.
            options = ['process', '--input', str(crop_path), '--target', 'creature', '--mode', 'animation', '--output-dir', str(qc), '--rows', '2', '--cols', '2', '--cell-size', str(CELL), '--scale-strategy', 'preserve', '--fit-scale', '0.80', '--shared-scale', '--align', 'feet', '--trim-border', '0', '--edge-touch-margin', '1', '--component-mode', 'largest', '--duration', '240', '--reject-edge-touch', '--strict-qc', '--prompt-file', str(ART/'prompts'/f'{morph}-{action}.txt')]
            if action == 'feed':
                options += ['--write-scale-profile', str(profile), '--profile-name', morph+'-'+stage]
            elif profile.exists():
                options += ['--scale-profile', str(profile), '--max-profile-scale-drift', '0.18']
            else:
                failures.append({'morph':morph,'stage':stage,'action':action,'error':'Accepted feed scale profile missing'})
                continue
            parsed = processor.build_parser().parse_args(options)
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    processor.cmd_process(parsed)
            except ValueError as error:
                failures.append({'morph':morph,'stage':stage,'action':action,'error':str(error)})
                continue
            out.mkdir(parents=True, exist_ok=True)
            sheet = Image.open(qc/'sheet-transparent.png').convert('RGBA')
            # Each logical pixel becomes a literal 2x2 block in exported 96px cells.
            sheet.resize((192,192), Image.Resampling.NEAREST).save(out/(action+'.png'), optimize=True)
            frames = [Image.open(qc/f'animation-{i+1}.png').convert('RGBA').resize((96,96), Image.Resampling.NEAREST) for i in range(4)]
            processor.save_transparent_gif(frames, out/(action+'.gif'), 240)
            if action == 'feed':
                frames[0].save(out/'idle.png', optimize=True)
            record = {'processorVersion':PROCESSOR_VERSION, 'morphId':morph, 'stage':stage, 'action':action, 'frames':4, 'cellSize':96, 'logicalCellSize':48, 'sourceSha256':source_hash, 'source':f'art-source/cre36/raw/{raw.name}', 'sheet':f'/assets/cre36/{morph}/{stage}/{action}.png', 'resampling':'nearest', 'horizontalAnchor':'fixed cell center', 'scaleProfile':str(profile.relative_to(ROOT))}
            record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n')
            count += 1
    print(json.dumps({'processedStageActions':count,'sheets':len(list(PUBLIC.glob('cre_*/*/feed.png'))),'failures':failures},ensure_ascii=False))
    (ART/'processing-status.json').write_text(json.dumps({'processorVersion':PROCESSOR_VERSION,'processedStageActions':count,'failures':failures},ensure_ascii=False,indent=2)+'\n')
    if failures:raise SystemExit(1)

if __name__ == '__main__':
    main()
