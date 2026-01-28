import { Navbar, Nav, Container } from 'react-bootstrap'
import { Link, useLocation } from 'react-router-dom'

function Navigation() {
  const location = useLocation()

  return (
    <Navbar 
      expand="lg" 
      className="mb-0" 
      style={{ 
        backgroundColor: '#ffffff', 
        borderBottom: '1px solid #e0e0e0',
        padding: '0.75rem 1rem'
      }}
    >
      <Container fluid>
        <Navbar.Brand as={Link} to="/" style={{ color: '#333333', fontWeight: 600, fontSize: '1rem' }}>
          <code style={{ color: '#0066cc' }}>weather-forecast</code>
        </Navbar.Brand>
        <Navbar.Toggle aria-controls="basic-navbar-nav" style={{ borderColor: '#e0e0e0' }} />
        <Navbar.Collapse id="basic-navbar-nav">
          <Nav className="me-auto">
            <Nav.Link 
              as={Link} 
              to="/" 
              style={{ 
                color: location.pathname === '/' ? '#0066cc' : '#666666',
                fontSize: '0.875rem',
                textTransform: 'uppercase',
                letterSpacing: '0.5px'
              }}
            >
              Dashboard
            </Nav.Link>
            <Nav.Link 
              as={Link} 
              to="/architecture" 
              style={{ 
                color: location.pathname === '/architecture' ? '#0066cc' : '#666666',
                fontSize: '0.875rem',
                textTransform: 'uppercase',
                letterSpacing: '0.5px'
              }}
            >
              Architecture
            </Nav.Link>
            <Nav.Link 
              as={Link} 
              to="/health" 
              style={{ 
                color: location.pathname === '/health' ? '#0066cc' : '#666666',
                fontSize: '0.875rem',
                textTransform: 'uppercase',
                letterSpacing: '0.5px'
              }}
            >
              Health
            </Nav.Link>
          </Nav>
          <Nav>
            <Navbar.Text style={{ color: '#666666', fontSize: '0.75rem', fontFamily: 'monospace' }}>
              API:5000 | Spark:8080 | Ray:8265
            </Navbar.Text>
          </Nav>
        </Navbar.Collapse>
      </Container>
    </Navbar>
  )
}

export default Navigation
