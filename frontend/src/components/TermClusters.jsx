import React, { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import './TermClusters.css';

function TermClusters({ clusters }) {
  const [collapsed, setCollapsed] = useState(false);
  const [showAll, setShowAll] = useState(false);
  
  if (!clusters || clusters.length === 0) return null;
  
  const displayClusters = showAll ? clusters : clusters.slice(0, 3);
  
  return (
    <div className="term-clusters">
      <div 
        className="clusters-header" 
        onClick={() => setCollapsed(!collapsed)} 
        style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', userSelect: 'none' }}
      >
        {collapsed ? <ChevronRight size={18} /> : <ChevronDown size={18} />}
        <span className="clusters-title" style={{ marginLeft: 8 }}>Кластеры терминов</span>
        {clusters.length > 3 && !collapsed && (
          <button 
            className="toggle-clusters" 
            onClick={(e) => { e.stopPropagation(); setShowAll(!showAll); }}
            style={{ marginLeft: 'auto' }}
          >
            {showAll ? 'Свернуть' : `Показать все (${clusters.length})`}
          </button>
        )}
      </div>
      {!collapsed && (
        <div className="clusters-list">
          {displayClusters.map((cluster, idx) => (
            <div key={idx} className="cluster-item">
             <div className="cluster-terms">
               {cluster.terms.map((term, i) => (
                 <span key={i} className="cluster-term">{term}</span>
               ))}
             </div>
             <div className={`cluster-status ${cluster.is_negated ? 'negated' : 'positive'}`}>
               {cluster.is_negated ? 'Отрицается' : 'Требуется'}
             </div>
           </div>
          ))}
        </div>
      )}
    </div>
  );
}

// function TermClusters({ clusters }) {
//   const [expanded, setExpanded] = useState(false);
  
//   if (!clusters || clusters.length === 0) return null;
  
//   const displayClusters = expanded ? clusters : clusters.slice(0, 3);
  
//   return (
//     <div className="term-clusters">
//       <div className="clusters-header">
//         <span className="clusters-title">Кластеры терминов</span>
//         {clusters.length > 3 && (
//           <button className="toggle-clusters" onClick={() => setExpanded(!expanded)}>
//             {expanded ? 'Свернуть' : `Показать все (${clusters.length})`}
//           </button>
//         )}
//       </div>
//       <div className="clusters-list">
//         {displayClusters.map((cluster, idx) => (
//           <div key={idx} className="cluster-item">
//             <div className="cluster-terms">
//               {cluster.terms.map((term, i) => (
//                 <span key={i} className="cluster-term">{term}</span>
//               ))}
//             </div>
//             <div className={`cluster-status ${cluster.is_negated ? 'negated' : 'positive'}`}>
//               {cluster.is_negated ? 'Отрицается' : 'Требуется'}
//             </div>
//           </div>
//         ))}
//       </div>
//     </div>
//   );
// }

export default TermClusters;