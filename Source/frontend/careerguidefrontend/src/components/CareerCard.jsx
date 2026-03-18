import { Briefcase, Target } from 'lucide-react';
import './CareerCard.css';

export default function CareerCard({ alignment }) {
  if (!alignment) return null;

  return (
    <div className="glass-panel career-card">
      <div className="career-header">
        <Briefcase className="text-gradient" size={24} />
        <h2>Career Alignment</h2>
      </div>

      <div className="career-content">
        <div className="track-badge">
          <Target size={16} />
          <span>{alignment.career_track}</span>
        </div>
        <p className="alignment-reason">{alignment.alignment_reason}</p>
      </div>
    </div>
  );
}
