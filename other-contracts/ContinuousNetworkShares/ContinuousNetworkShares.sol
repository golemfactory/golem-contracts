pragma solidity ^0.6.6;

import "./IERC20.sol";

//kontrakt do redystrybucji zgromadzonych fee pomiędzy token holders, którzy mają stake
contract ContinuousNetworkShares {

  uint256 perUnit = 0;                        //unit to duży GNT czyli 10^18 małych GNT
	                                      //ile sumarycznie przypada dywidend na jeden unit od utworzenia kontraktu
  mapping(address => uint256) stake;          //jak nazwa mówi, małe GNT dla ścisłości
  uint256 totalStake = 0;                     //suma stake, małych GNT dla ścisłości
  mapping(address => uint256) myLastPerUnit;  //wartość perUnit w momencie ostatniego wywołania funkcji na stake przez staker
	                                      //funkcje: collect, withdraw, deposit
  IERC20 gnt;                              //adres kontraktu gnt
  IERC20 dai;                                  //adres kontraktu dai, to może być dowolny token ERC20, tutaj nazwa dla lepszej intuicji
  uint256 lastBalance = 0;                    //balance dai dla tego adresu, po ostatniej aktualizacji
  
  constructor(IERC20 _gnt, IERC20 _dai) public {     
    gnt = _gnt;
    dai = _dai;
  }
	
  function _collect(address staker) private {
    if (totalStake >= 10**18) {             //żeby nie dzielić przez zero, do przemyślenia else
      perUnit = perUnit + (dai.balanceOf(address(this))-lastBalance)/(totalStake/10**18);   //przyrost należnych dywidend per unit
      lastBalance = dai.balanceOf(address(this));                    //ważne aby zrobić po transfer
    }
    if (stake[staker] >= 10**18) {          //jeśli mniejsze to i tak nie ma czego wypłacić
      uint256 value = (perUnit-myLastPerUnit[staker])*(stake[staker]/(10**18)); //to jest krytyczne
		                                                               //między czasem ostatniej aktualizacji lastPerUnit[staker] i teraz stake się nie zmienił
                                                                   //ponadto na konto dai był tylko wpływ fee
      if (value > 0) {
	    dai.transfer(staker, value);
        lastBalance = lastBalance - value;                    //ważne aby zrobić po transfer
      }
    }
    myLastPerUnit[staker] = perUnit;
  }
  
  function getStake(address staker) public view returns (uint256) {
      return stake[staker];
  }
	
  function getTotalStake() public view returns (uint256) {
      return totalStake;
  }
	
  function collect() public {                  //wypłać swoje dywidendy
    _collect(msg.sender);
  }
	
  function withdraw() public {                 //wypłać stake
    require(stake[msg.sender] > 0);
    _collect(msg.sender);
    require(gnt.transfer(msg.sender, stake[msg.sender]));
    totalStake = totalStake - stake[msg.sender];
    delete stake[msg.sender];
    delete myLastPerUnit[msg.sender];
  }
	
  function deposit(uint256 value) public {  //wpłać stake, wywołuje transferFrom
    require(value > 0);
    require(gnt.transferFrom(msg.sender, address(this), value));
    _collect(msg.sender);        //przy okazji aktualizuje myLastPerUnit[staker]
    stake[msg.sender] = stake[msg.sender] + value;
    totalStake = totalStake + value;
  }
  
  function emergencyTransfer(address _to, uint256 value) public {        //jeśli ktoś przez pomyłkę przeleje gnt funkcją transfer
                                                                            //to Golem uznaniowo może mu zwrócić środki
    require(gnt.balanceOf(address(this)) >= totalStake + value);
    gnt.transfer(_to, value);
  }
}
