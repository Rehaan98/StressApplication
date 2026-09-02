import React from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { friendlyFeature } from '@/lib/labels';

interface ShapDriver {
  feature: string;
  shap_value: number;
  impact: string;
}

interface ShapBarChartProps {
  drivers: ShapDriver[];
}

export const ShapBarChart: React.FC<ShapBarChartProps> = ({ drivers }) => {
  const data = drivers.map(d => ({
    name: friendlyFeature(d.feature),
    shap: d.shap_value,
    color: d.shap_value > 0 ? '#ef4444' : '#10b981'
  }));

  return (
    <div className="w-full h-72">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 10, right: 30, left: 20, bottom: 10 }}>
          <XAxis type="number" stroke="#94a3b8" fontSize={12} />
          <YAxis dataKey="name" type="category" stroke="#cbd5e1" fontSize={11} width={150} />
          <Tooltip
            contentStyle={{ backgroundColor: '#1e293b', borderColor: '#475569', borderRadius: '8px', color: '#fff' }}
            formatter={(value: any) => [`${value}`, 'Effect on stress']}
          />
          <Bar dataKey="shap" radius={[0, 4, 4, 0]}>
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.color} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};
