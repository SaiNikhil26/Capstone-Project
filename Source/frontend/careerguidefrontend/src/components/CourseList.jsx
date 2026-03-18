import { Star, Building2, ExternalLink, Network, Signal } from 'lucide-react';
import './CourseList.css';

export default function CourseList({ stages }) {
  if (!stages || stages.length === 0) return null;

  return (
    <div className="course-list-container">
      {stages.map((stage, sIdx) => (
        <div key={sIdx} className="pathway-stage">
          <div className="stage-header">
            <div className="stage-indicator">{sIdx + 1}</div>
            <h3>{stage.stage}</h3>
          </div>
          
          <div className="courses-grid">
            {stage.courses.map((course, cIdx) => (
              <a 
                key={cIdx} 
                href={course.course_url || '#'} 
                target="_blank" 
                rel="noreferrer"
                className="course-card glass-panel"
              >
                <div className="card-top">
                  <div className="difficulty-badge" data-level={(course.difficulty || 'unknown').toLowerCase()}>
                    {course.difficulty || 'Mixed'}
                  </div>
                  {course.rating && (
                    <div className="rating">
                      <Star size={14} className="star-icon" fill="currentColor" />
                      <span>{course.rating}</span>
                    </div>
                  )}
                </div>

                <h4 className="course-title">{course.course_name}</h4>
                
                <div className="provider">
                  <Building2 size={14} />
                  <span>{course.organization || 'University'}</span>
                </div>

                {course.skills && (
                  <div className="skills-preview">
                    <p>{course.skills.length > 80 ? course.skills.substring(0, 80) + '...' : course.skills}</p>
                  </div>
                )}
                
                <div className="card-footer">
                  <span className="view-link">View Course <ExternalLink size={14} /></span>
                </div>
              </a>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
