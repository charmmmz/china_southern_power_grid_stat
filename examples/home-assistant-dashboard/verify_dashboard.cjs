const fs=require('fs');
const assert=require('assert/strict');
const config=JSON.parse(fs.readFileSync(__dirname+'/electricity.yaml','utf8'));
const p='sensor.csgaccount_example_account_example_account_';
const current=[{date:'2026-10-01',kwh:16.85},{date:'2026-10-02',kwh:23.12},{date:'2026-10-03',kwh:25.81}];
const previous=Array.from({length:30},(_,i)=>({date:'2026-09-'+String(i+1).padStart(2,'0'),kwh:20}));
const states=Object.fromEntries(['balance','arrears','this_year_total_usage','this_year_total_cost','last_year_total_usage','last_year_total_cost'].map(s=>[p+s,{state:'0',attributes:{}}]));
Object.assign(states,{[p+'this_month_total_usage']:{state:'65.78',attributes:{this_month_by_day:current}},[p+'last_month_total_usage']:{state:'515.12',attributes:{last_month_by_day:previous}},[p+'latest_day_kwh']:{state:'25.81',attributes:{latest_day_date:'2026-10-03'}},[p+'last_month_total_cost']:{state:'354.13',attributes:{billing_month:'202609'}}});
function render(value,entity,variables,statesArg=states){
 if(typeof value!=='string'||!value.startsWith('[[['))return value;
 return Function('entity','variables','states',value.slice(3,-3))(entity,variables,statesArg);
}
function cardData(card,statesArg=states){
 const template=config.button_card_templates[card.template];
 const entity=statesArg[card.entity];
 const vars=Object.assign({},template.variables,card.variables);
 for(const key of Object.keys(vars).sort())vars[key]=render(vars[key],entity,vars,statesArg);
 return {entity,vars,template};
}
for(const section of config.views[0].sections){
 for(const card of section.cards){
  if(!card.template)continue;
  const {entity,vars,template}=cardData(card);
  for(const field of ['name','label','state_display']){
   const value=render(card[field]??template[field],entity,vars);
   if(value!==undefined)console.log(card.name?.startsWith('[[[')?card.entity.replace(p,''):card.name,field,value);
  }
  const missing=cardData(card,{});
  for(const field of ['name','label','state_display'])render(card[field]??template[field],undefined,missing.vars,{});
 }
}
const month=config.views[0].sections[0].cards[1];
const d=cardData(month).vars.a_data;
assert.equal(d.monthAverage.toFixed(2),'21.93');
assert.equal(d.comparison.days,3);
assert.equal(d.comparison.percent.toFixed(1),'9.6');
assert.equal(d.billLabel,'2026 年 9 月');
const missing=cardData(month,{}).vars.a_data;
assert.equal(missing.monthAverage,null);assert.equal(missing.comparison,null);
const gap=structuredClone(states);gap[p+'last_month_total_usage'].attributes.last_month_by_day.splice(1,1);
assert.equal(cardData(month,gap).vars.a_data.comparison,null);
const zero=structuredClone(states);zero[p+'this_month_total_usage'].state='0';zero[p+'this_month_total_usage'].attributes.this_month_by_day=[{date:'2026-10-01',kwh:0},{date:'2026-10-02',kwh:null}];
assert.equal(cardData(month,zero).vars.a_data.current.length,1);
assert.equal(cardData(month,zero).vars.a_data.monthAverage,0);
const series=config.views[0].sections[2].cards[1].series[0];
const chart=Function('entity','hass','start','end',series.data_generator)(states[p+'this_month_total_usage'],{states},new Date('2026-09-20'),new Date('2026-10-04'));
assert.equal(chart.length,14);assert.equal(chart.at(-1)[1],25.81);
assert.equal(/latest_day_cost|current_ladder|this_month_total_cost|\.charge|日费用|本月累计电费/.test(JSON.stringify(config)),false);
console.log('PASS: display templates, missing states, real zero, partial periods, bill month and 14-day daily-only chart');
