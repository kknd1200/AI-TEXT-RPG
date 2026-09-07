import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import { fileURLToPath } from 'node:url';
import { resolve, dirname } from 'node:path';

const root=fileURLToPath(new URL('../',import.meta.url));
const tar=gunzipSync(readFileSync(resolve(root,'art-source/cre36/runtime-sprites.tar.gz')),{maxOutputLength:64*1024*1024});
let count=0;
for(let offset=0;offset+512<=tar.length;){
  const header=tar.subarray(offset,offset+512);
  if(header.every(b=>b===0))break;
  const name=header.subarray(0,100).toString('utf8').split('\0')[0];
  const sizeText=header.subarray(124,136).toString('ascii').replace(/\0/g,'').trim();
  if(!/^[0-7]+$/.test(sizeText))throw Error('Invalid asset bundle size');
  const size=parseInt(sizeText,8);
  if(!/^public\/assets\/(cre36\/(atlases|fx)|geckos\/(baby|adult))\/[a-z0-9_-]+\.png$/.test(name))throw Error('Unexpected asset bundle path');
  if(![0,48].includes(header[156])||offset+512+size>tar.length)throw Error('Invalid asset bundle entry');
  const path=resolve(root,name);
  mkdirSync(dirname(path),{recursive:true});
  writeFileSync(path,tar.subarray(offset+512,offset+512+size));
  count++;
  offset+=512+Math.ceil(size/512)*512;
}
console.log(`Restored ${count} generated PNG assets from the committed bundle.`);
