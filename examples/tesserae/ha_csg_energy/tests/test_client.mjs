import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
const source = await readFile(new URL('../client.js', import.meta.url), 'utf8');
const {default:render} = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
const manifest = JSON.parse(await readFile(new URL('../plugin.json', import.meta.url), 'utf8'));
function html(data,fragment='full',options={}){const shadow={innerHTML:''};render(shadow,{data,cell:{fragment,options}});return shadow.innerHTML.replace(/<style>[\s\S]*?<\/style>/g,'');}
test('legacy cost options show real kWh and previous bill',()=>{
 const output=html(manifest.data_schema.sample,'full',{metric:'cost',show_ladder:true});
 assert.match(output,/60\.00/); assert.match(output,/22\.00/); assert.match(output,/288\.00/);
 assert.doesNotMatch(output,/DAILY COST|LADDER TARIFF|CURRENT RATE/);
});
test('null and absent quantities never become zero',()=>{
 const output=html({month:{total_kwh:null},latest:{kwh:null},previous_month:{total_cost:null}});
 assert.doesNotMatch(output,/0\.00|¥/); assert.match(output,/BILL NOT AVAILABLE/);
});
test('a real zero bill remains a reported bill',()=>{
 const output=html({previous_month:{period:'2026-09',billing_month:'2026-09',total_cost:0}},'billing');
 assert.match(output,/0\.00/);assert.match(output,/ISSUED BILL/);
});
test('legacy fragments resolve to usage and billing',()=>{
 assert.match(html(manifest.data_schema.sample,'cost_trend'),/DAILY USAGE/);
 assert.match(html(manifest.data_schema.sample,'ladder'),/LAST MONTH BILL/);
});
test('missing dates do not draw a connected line',()=>{
 const output=html({series:[{date:'2026-10-01',kwh:10},{date:'2026-10-03',kwh:20}]},'trend');
 assert.doesNotMatch(output,/class="segment"/); assert.match(output,/10\/3/);
});
test('zero usage renders as a valid single point',()=>{
 const output=html({series:[{date:'2026-10-01',kwh:0}]},'trend');
 assert.match(output,/class="point"/); assert.doesNotMatch(output,/Waiting for/);
});

test('average comparison appears under daily average and reported days appear once',()=>{
 const output=html(manifest.data_schema.sample);
 const average=output.match(/<section class="stat average-stat">([\s\S]*?)<\/section>/)[1];
 assert.match(average,/25\.0%/);assert.match(average,/SEP 16\.00/);
 assert.doesNotMatch(output,/59\.3%/);
 assert.equal((output.match(/3 REPORTED DAYS/g)||[]).length,1);
});
